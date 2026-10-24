"""The hosted workspace's database (supabase/migrations), run on a real local Postgres.

The tests start a scratch Postgres cluster, add a stand-in for Supabase's auth schema and roles
(tests/hosted_supabase_stub.sql), run the migration, and act as each person the way PostgREST
does for a request: one transaction, the authenticated role, and the caller's id in
request.jwt.claims. They check that:

- a Contributor cannot record a decision; a brief's author is the caller whatever the client
  sends; every timestamp is the server's;
- an Editor's approval of their own brief is refused with four-eyes on, and an approval naming
  the wrong SHA-256 is refused; a brief whose SHA-256 is not its draft's is refused, and the
  database's canonical JSON gives the page's SHA-256 for every template brief;
- a brief lists the reviewer notes its draft answers, and answers each once and no other; a
  brief that carries a lesson is refused, since the hosted version has none yet;
- the restricted layer's outcomes go through the same four-eyes workflow, on synthetic case ids
  only;
- nobody, the dashboard included, updates or deletes briefs, decisions or the audit log, and no
  audited table can be truncated;
- every action leaves an audit row with the right actor, written by the database;
- the workflow, the roles and the private drafts hold.

They need Postgres (initdb, pg_ctl and psql) and are skipped without it. As root, the cluster
runs as the postgres user, since initdb refuses to run as root. A rise in exports is a lead, not
evidence of a breach.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import random
import re
import shutil
import string
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from radar.brief.fake_llm import FAKE_ANSWER, fake_draft

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
STUB = ROOT / "tests" / "hosted_supabase_stub.sql"
BRIEFS = ROOT / "app" / "data" / "briefs"
NODE = shutil.which("node")
RUN = "2026-10"
SCREEN = {"ok": True, "rules": "radar-brief-screen/2", "checked_at": "2026-10-22T09:00:00.000Z"}


def _pg_bin() -> Path | None:
    for cand in [os.environ.get("DR_PG_BIN"), *(str(Path(p).parent) for p in [shutil.which("initdb")] if p),
                 *sorted(glob.glob("/usr/lib/postgresql/*/bin"), key=lambda p: int(re.sub(r"\D", "", p) or 0), reverse=True),
                 "/usr/local/bin", "/opt/homebrew/bin"]:
        if cand and all((Path(cand) / b).exists() for b in ("initdb", "pg_ctl", "psql")):
            return Path(cand)
    return None


PG_BIN = _pg_bin()
pytestmark = pytest.mark.skipif(PG_BIN is None, reason="Postgres (initdb, pg_ctl, psql) is not installed")


class Refused(Exception):
    pass


class Db:
    """One scratch database. sql() runs as the database owner, as the dashboard's SQL editor does;
    as_() runs one request as a person."""

    def __init__(self, socket_dir: Path, name: str = "workspace"):
        self.cmd = [str(PG_BIN / "psql"), "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-h", str(socket_dir), "-U", "postgres", "-d", name]

    def _run(self, text: str) -> list[str]:
        r = subprocess.run(self.cmd, input=text, capture_output=True, text=True)
        if r.returncode != 0:
            m = re.search(r"ERROR:\s+(.*)", r.stderr)
            raise Refused(m.group(1).strip() if m else r.stderr.strip())
        return [line for line in r.stdout.splitlines() if line != ""]

    def sql(self, text: str) -> list[str]:
        return self._run(text)

    def as_(self, who: str | None, text: str, role: str = "authenticated") -> list[str]:
        claims = {"role": role}
        if who:
            claims["sub"] = who
        return self._run(f"begin;\nset local role {role};\nset local request.jwt.claims to {lit(json.dumps(claims))};\n{text};\ncommit;\n")

    def refused(self, who: str | None, text: str, role: str = "authenticated") -> str:
        with pytest.raises(Refused) as e:
            self.as_(who, text, role)
        return str(e.value)

    def one(self, text: str) -> str:
        rows = self.sql(text)
        assert len(rows) == 1, rows
        return rows[0]


def lit(s: str) -> str:
    tag = "q" + "".join(random.choices(string.ascii_lowercase, k=8))
    assert f"${tag}$" not in s
    return f"${tag}${s}${tag}$"


def jlit(v) -> str:
    return f"{lit(json.dumps(v))}::jsonb"


def canon(v) -> str:
    """The page's canonical JSON for drafts (strings, booleans, null, arrays, objects with ASCII keys)."""
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(draft: dict) -> str:
    return hashlib.sha256(canon(draft).encode("utf-8")).hexdigest()


def b36(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + out
    return out or "0"


def new_id(file_id: str) -> str:
    return f"{file_id}~{b36(int(time.time() * 1000))}~{''.join(random.choices('0123456789abcdefghijklmnopqrstuvwxyz', k=4))}"


@pytest.fixture(scope="module")
def ctx() -> dict:
    return json.loads((BRIEFS / "kazakhstan-851762.json").read_text(encoding="utf-8"))


def brief_for(ctx: dict, review: list | None = None) -> dict:
    """The page's template brief for the context (radar/brief/fake_llm.py's fake_draft), answering
    each reviewer note with a sentence."""
    return fake_draft(ctx, review or None, FAKE_ANSWER if review else None)


def outcome_for(case_file: str, outcome: str = "more_information", note: str = "The forwarder's role needs the exporter's own papers first.") -> dict:
    return {"schema": "radar-case-outcome/1", "case_id": case_file[len("case_"):], "outcome": outcome, "note": note}


@pytest.fixture(scope="module")
def db():
    base = Path(tempfile.mkdtemp(prefix="radar-workspace-pg-"))
    prefix: list[str] = []
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        import pwd
        try:
            pw = pwd.getpwnam("postgres")
        except KeyError:
            pytest.skip("running as root and there is no postgres user to run the cluster")
        os.chown(base, pw.pw_uid, pw.pw_gid)
        if not shutil.which("runuser"):
            pytest.skip("running as root without runuser")
        prefix = ["runuser", "-u", "postgres", "--"]
    data = base / "data"
    run = lambda args: subprocess.run(prefix + [str(a) for a in args], check=True, capture_output=True, text=True)  # noqa: E731
    run([PG_BIN / "initdb", "-D", data, "-U", "postgres", "-A", "trust", "-E", "UTF8", "--locale=C"])
    run([PG_BIN / "pg_ctl", "-D", data, "-o", f"-k {base} -c listen_addresses='' -c fsync=off", "-l", base / "log", "-w", "start"])
    try:
        Db(base, "postgres").sql("create database workspace")
        d = Db(base)
        d.sql("alter database workspace set timezone to 'UTC'")   # as on Supabase
        d.sql(STUB.read_text(encoding="utf-8"))
        assert MIGRATIONS, "no migration in supabase/migrations"
        for m in MIGRATIONS:
            d.sql(m.read_text(encoding="utf-8"))
        yield d
    finally:
        subprocess.run(prefix + [str(PG_BIN / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"], capture_output=True)
        shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(scope="module")
def people(db):
    """Made-up people at every level, plus one signed-in person who is not a member and one whose
    access was removed. Ids are random, so no fixed number appears in the repo; emails are role
    labels at a test domain."""
    roles = {"owner": "owner", "editor": "editor", "editor2": "editor", "contributor": "contributor",
             "contributor2": "contributor", "viewer": "viewer", "removed": "contributor"}
    ids = {k: str(uuid.uuid4()) for k in [*roles, "outsider"]}
    db.sql("insert into auth.users (id, email) values " + ", ".join(f"('{v}', '{'@'.join([k, 'workspace.test'])}')" for k, v in ids.items()))
    db.sql("insert into public.members (user_id, role, display_name) values "
           + ", ".join(f"('{ids[k]}', '{r}', 'Analyst {k}')" for k, r in roles.items()))
    db.sql(f"update public.members set active = false where user_id = '{ids['removed']}'")
    return ids


class Flow:
    """The page's calls, as the SQL that PostgREST runs for them (app/src/hosted.js)."""

    def __init__(self, db: Db, people: dict, ctx: dict):
        self.db, self.p, self.ctx = db, people, ctx

    def save(self, who: str, file_id: str, draft: dict | None = None, *, review: list | None = None, sha256: str | None = None) -> str:
        draft = draft or brief_for(self.ctx, review)
        bid = new_id(file_id)
        self.db.as_(self.p[who], "insert into public.briefs (id, lead, run, series, kind, source, draft, review, lessons, screen, sha256) values "
                    f"({lit(bid)}, '{file_id}', '{RUN}', {lit(self.ctx['series'])}, 'brief', 'template', {jlit(draft)}, {jlit(review or [])}, "
                    f"'[]'::jsonb, {jlit(SCREEN)}, '{sha256 or sha(draft)}')")
        key = f"{self.p[who]}/{bid}"
        self.pointer(who, file_id, "drafting", key)
        return key

    def propose(self, who: str, case_file: str, outcome: str = "more_information") -> str:
        draft = outcome_for(case_file, outcome)
        bid = new_id(case_file)
        self.db.as_(self.p[who], "insert into public.briefs (id, lead, run, series, kind, source, draft, sha256) values "
                    f"({lit(bid)}, '{case_file}', '{RUN}', 'EXP-0001 to Armenia', 'case_outcome', 'analyst', {jlit(draft)}, '{sha(draft)}')")
        key = f"{self.p[who]}/{bid}"
        self.pointer(who, case_file, "submitted", key)
        return key

    def pointer(self, who: str, file_id: str, status: str, key: str):
        self.db.as_(self.p[who], f"insert into public.files (lead, run, series, status, brief_id) values ('{file_id}', '{RUN}', 'x', '{status}', '{key}') "
                    f"on conflict (lead) do update set status = excluded.status, brief_id = excluded.brief_id")

    def submit(self, who: str, file_id: str, key: str):
        self.pointer(who, file_id, "submitted", key)

    def decide(self, who: str, file_id: str, decision: str, key: str | None, brief_sha: str | None, *, note: str | None = None, reason: str | None = None):
        if note is None and decision == "returned":
            note = "Say which onward check carries the lead."
        if note is None and decision == "rejected" and file_id.startswith("case_"):
            note = "The outcome does not follow from the questions worked."
        if reason is None and decision == "rejected" and not file_id.startswith("case_"):
            reason = "ordinary_trade"
        cols, vals = ["id", "lead", "run", "series", "decision", "brief_id", "brief_sha256"], [
            lit(new_id(file_id)), f"'{file_id}'", f"'{RUN}'", "'x'", f"'{decision}'", lit(key) if key else "null", lit(brief_sha) if brief_sha else "null"]
        if note is not None:
            cols.append("note"); vals.append(lit(note))  # noqa: E702
        if reason is not None:
            cols.append("reason"); vals.append(lit(reason))  # noqa: E702
        self.db.as_(self.p[who], f"insert into public.decisions ({', '.join(cols)}) values ({', '.join(vals)})")

    def brief_sha(self, key: str) -> str:
        return self.db.one(f"select sha256 from public.briefs where key = '{key}'")


@pytest.fixture()
def flow(db, people, ctx):
    return Flow(db, people, ctx)


def fresh_file(db: Db) -> str:
    used = set(db.sql("select lead from public.files union select lead from public.briefs union select lead from public.drafts "
                      "union select lead from public.events where lead is not null union select lead from public.private_drafts "
                      "union select lead from public.checks"))
    for a in string.ascii_uppercase:
        for b in string.ascii_uppercase:
            lead = f"{RUN}_{a}{b}-851762"
            if lead not in used:
                return lead
    raise AssertionError("no file id left")


def fresh_case(db: Db) -> str:
    used = set(db.sql("select lead from public.files union select lead from public.briefs union select lead from public.checks"))
    for n in range(1, 1000):
        cid = f"case_SYN-CASE-{n:03d}"
        if cid not in used:
            return cid
    raise AssertionError("no case id left")


def insert_brief(file_id: str, draft: dict, *, review: list | None = None, lessons: list | None = None, screen: dict | None = None,
                 kind: str = "brief", source: str = "template", run: str = RUN, series: str | None = None, sha256: str | None = None) -> str:
    return ("insert into public.briefs (id, lead, run, series, kind, source, draft, review, lessons, screen, sha256) values "
            f"({lit(new_id(file_id))}, '{file_id}', '{run}', {lit(series if series is not None else draft.get('series', 'x'))}, '{kind}', '{source}', "
            f"{jlit(draft)}, {jlit([] if review is None else review)}, {jlit(lessons or [])}, {jlit(screen) if screen is not None else jlit(SCREEN)}, "
            f"'{sha256 or sha(draft)}')")


# ============================================================== reads

TABLES = ["members", "briefs", "decisions", "files", "checks", "config", "audit", "events", "drafts"]


def test_members_read_and_nobody_else_does(db, people, flow):
    flow.save("contributor", fresh_file(db))
    assert int(db.as_(people["viewer"], "select count(*) from public.briefs")[0]) >= 1
    for t in TABLES:
        # Signed in but not a member, or a member whose access was removed: nothing.
        assert db.as_(people["outsider"], f"select count(*) from public.{t}") == ["0"], t
        assert db.as_(people["removed"], f"select count(*) from public.{t}") == ["0"], t
        # Not signed in at all: no access to the table.
        assert "permission denied" in db.refused(None, f"select count(*) from public.{t}", role="anon"), t


# ============================================================== who and when

def test_a_contributor_cannot_record_a_decision(db, people, flow):
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    flow.submit("contributor", lead, key)
    msg = db.refused(people["contributor2"], f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256) "
                     f"values ({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', 'approved', '{key}', '{flow.brief_sha(key)}')")
    assert "only an Editor or the owner" in msg or "row-level security" in msg
    assert db.one(f"select count(*) from public.decisions where lead = '{lead}'") == "0"


def test_a_briefs_author_is_the_caller_whatever_the_client_sends(db, people, flow, ctx):
    lead = fresh_file(db)
    draft = brief_for(ctx)
    bid = new_id(lead)
    db.as_(people["contributor"], f"insert into public.briefs (id, author, lead, run, series, source, draft, screen, sha256) values "
           f"({lit(bid)}, '{people['editor']}', '{lead}', '{RUN}', {lit(ctx['series'])}, 'template', {jlit(draft)}, {jlit(SCREEN)}, '{sha(draft)}')")
    assert db.one(f"select author from public.briefs where id = {lit(bid)}") == people["contributor"]
    key = f"{people['contributor']}/{bid}"
    assert db.one(f"select key from public.briefs where id = {lit(bid)}") == key
    # The same for a decision: the caller, never the author the client names.
    flow.submit("contributor", lead, key)
    did = new_id(lead)
    db.as_(people["editor"], f"insert into public.decisions (id, author, lead, run, series, decision, brief_id, brief_sha256) values "
           f"({lit(did)}, '{people['owner']}', '{lead}', '{RUN}', 'x', 'approved', '{key}', '{sha(draft)}')")
    assert db.one(f"select author from public.decisions where id = {lit(did)}") == people["editor"]


def test_every_timestamp_comes_from_the_server(db, people, ctx):
    lead = fresh_file(db)
    draft = brief_for(ctx)
    bid = new_id(lead)
    old = "'2001-02-03T04:05:06Z'"
    db.as_(people["contributor"], f"insert into public.briefs (id, lead, run, series, source, draft, screen, sha256, created_at, version) values "
           f"({lit(bid)}, '{lead}', '{RUN}', {lit(ctx['series'])}, 'template', {jlit(draft)}, "
           f"{jlit(dict(SCREEN, checked_at='2001-02-03'))}, '{sha(draft)}', {old}, 42)")
    key = f"{people['contributor']}/{bid}"
    db.as_(people["contributor"], f"insert into public.files (lead, run, series, status, brief_id, updated_at, updated_by, assignee, assigned_at) values "
           f"('{lead}', '{RUN}', 'x', 'submitted', '{key}', {old}, '{people['owner']}', '{people['contributor']}', {old})")
    db.as_(people["contributor"], f"insert into public.checks (lead, check_id, state, updated_by, updated_at) values "
           f"('{lead}', 'chpl-end-destination', 'done', '{people['owner']}', {old})")
    db.as_(people["viewer"], f"insert into public.events (lead, run, action, detail, actor, at) values "
           f"('{lead}', '{RUN}', 'pack_exported', 'evidence pack (.md)', '{people['owner']}', {old})")
    db.as_(people["editor"], f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256, decided_at, four_eyes) values "
           f"({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', 'approved', '{key}', '{sha(draft)}', {old}, false)")
    recent = "> now() - interval '10 minutes'"
    for q in [f"select created_at {recent} and version = 1 and (screen ->> 'checked_at')::timestamptz {recent} from public.briefs where id = {lit(bid)}",
              f"select updated_at {recent} and assigned_at {recent} and updated_by = '{people['contributor']}' from public.files where lead = '{lead}'",
              f"select updated_at {recent} and updated_by = '{people['contributor']}' from public.checks where lead = '{lead}'",
              f"select decided_at {recent} and four_eyes from public.decisions where lead = '{lead}'",
              f"select at {recent} and actor = '{people['viewer']}' from public.events where lead = '{lead}'",
              f"select bool_and(at {recent}) from public.audit where lead = '{lead}'"]:
        assert db.one(q) == "t", q


# ============================================================== fingerprints and four-eyes

def test_a_brief_must_carry_its_drafts_sha256_and_be_for_its_file(db, people, ctx):
    lead = fresh_file(db)
    draft = brief_for(ctx)
    c = people["contributor"]
    other = dict(draft, headline=dict(draft["headline"], text=draft["headline"]["text"] + " Read with the limits."))
    assert "SHA-256 does not match the draft" in db.refused(c, insert_brief(lead, draft, sha256=sha(other)))
    # A draft for another series or run, a draft of another kind, or one the screen did not pass.
    assert "this file's series and run" in db.refused(c, insert_brief(lead, draft, series="India 851762"))
    assert "this file's series and run" in db.refused(c, insert_brief(lead, dict(draft, schema="radar-brief/2")))
    assert "run is not the file's run" in db.refused(c, insert_brief(lead, dict(draft, run="2026-09"), run="2026-09"))
    assert "passed the screen" in db.refused(c, insert_brief(lead, draft, screen=dict(SCREEN, ok=False)))
    assert "passed the screen" in db.refused(c, insert_brief(lead, draft, screen={"ok": True}))
    assert "drafted by Claude, from the template or edited" in db.refused(c, insert_brief(lead, draft, source="analyst"))
    assert "not a brief" in db.refused(c, insert_brief(fresh_case(db), draft))
    assert "not a brief" in db.refused(c, insert_brief(fresh_case(db), draft, kind="case_outcome"))
    # File ids are a run's corridor and code, or a synthetic case, on every table.
    for bad in ["2026-10_KZ-851762'; --", "case_CASE-001", "case_SYN-CASE-0001", "KZ-851762", "2026-10_kz-851762"]:
        for t, cols, vals in [("files", "lead", f"{lit(bad)}"), ("checks", "lead, check_id, state", f"{lit(bad)}, 'chpl-end-destination', 'done'"),
                              ("events", "lead, action", f"{lit(bad)}, 'pack_exported'"), ("private_drafts", "lead", f"{lit(bad)}")]:
            assert "check constraint" in db.refused(c, f"insert into public.{t} ({cols}) values ({vals})"), (t, bad)
        db.refused(c, insert_brief(bad.replace("'", ""), draft))   # by a check constraint, or first by the trigger's run check
    assert db.one(f"select count(*) from public.briefs where lead = '{lead}'") == "0"


def test_a_brief_lists_the_reviewer_notes_its_draft_answers(db, people, flow, ctx):
    lead = fresh_file(db)
    note = {"id": "review-1", "kind": "returned", "at": "2026-10-22", "text": "Say which onward check carries the lead."}
    key = flow.save("contributor", lead, review=[note])
    assert json.loads(db.one(f"select review from public.briefs where key = '{key}'")) == [note]
    assert db.one(f"select review from public.briefs where key = '{flow.save('contributor', lead)}'") == "[]"
    answered = brief_for(ctx, [note])
    c = people["contributor"]
    answer_twice = dict(answered, responds_to_review=answered["responds_to_review"] * 2)
    for draft, review, words in [
        (answered, [], "answer each reviewer note"),                                  # an answer to a note it does not list
        (brief_for(ctx), [note], "answer each reviewer note"),                        # a note it does not answer
        (answer_twice, [note], "answer each reviewer note"),                          # a note answered twice
        (answered, [note, note], "its own id"),
        (answered, [dict(note, id="note-1")], "its own id"),
        (answered, [dict(note, kind="approved")], "its own id"),
        (answered, [{"id": "review-1", "kind": "returned"}], "its own id"),
        (answered, [dict(note, at=20261022)], "its own id"),
        (answered, ["review-1"], "its own id"),
        (answered, [dict(note, id=f"review-{i}") for i in range(1, 6)] + [note], "its own id"),   # six notes: five ids at most
        (answered, [dict(note, text="x" * 9000)], "check constraint"),
        (answered, {"review-1": note}, "must be a list"),
    ]:
        assert words in db.refused(c, insert_brief(lead, draft, review=review)), (review, words)


def test_the_hosted_version_refuses_lessons(db, people, ctx):
    lead = fresh_file(db)
    lesson = {"key": "u/d", "id": "lesson-1", "scope": {"route": "KZ-851762"}, "text": "Check re-exports before the onward check.", "sha256": "0" * 64}
    assert "no lessons yet" in db.refused(people["contributor"], insert_brief(lead, brief_for(ctx), lessons=[lesson]))
    # A decision cannot be about a lesson either: the hosted decisions are the four on a file.
    assert "no lessons yet" in db.refused(people["editor"], f"insert into public.decisions (id, lead, run, series, decision, reason) "
                                          f"values ({lit(new_id('lesson'))}, '{lead}', '{RUN}', 'x', 'lesson_approved', 'other')")


def test_an_editors_own_brief_cannot_be_approved_with_four_eyes_on(db, people, flow):
    lead = fresh_file(db)
    key = flow.save("editor", lead)
    flow.submit("editor", lead, key)
    ins = lambda extra="": (f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256{', four_eyes' if extra else ''}) "  # noqa: E731
                            f"values ({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', 'approved', '{key}', '{flow.brief_sha(key)}'{extra})")
    assert "four-eyes is on" in db.refused(people["editor"], ins())
    # The four-eyes flag a client sends is ignored: the database reads the setting.
    assert "four-eyes is on" in db.refused(people["editor"], ins(", false"))
    # Another editor can approve it; with four-eyes off the author can, and the decision says it was off.
    flow.decide("editor2", lead, "approved", key, flow.brief_sha(key))
    assert db.one(f"select four_eyes from public.decisions where lead = '{lead}'") == "t"
    lead2 = fresh_file(db)
    key2 = flow.save("editor", lead2)
    flow.submit("editor", lead2, key2)
    db.as_(people["editor2"], "update public.config set four_eyes = false where key = 'workflow'")
    try:
        flow.decide("editor", lead2, "approved", key2, flow.brief_sha(key2))
        assert db.one(f"select four_eyes from public.decisions where lead = '{lead2}'") == "f"
    finally:
        db.as_(people["editor2"], "update public.config set four_eyes = true where key = 'workflow'")


def test_an_approval_naming_the_wrong_sha256_is_refused(db, people, flow, ctx):
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    flow.submit("contributor", lead, key)
    wrong = sha(dict(brief_for(ctx), run="2026-09"))
    for sha_sql in [f"'{wrong}'", "null"]:
        msg = db.refused(people["editor"], f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256) "
                         f"values ({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', 'approved', '{key}', {sha_sql})")
        assert "SHA-256 does not match the brief" in msg
    # A brief of another file cannot be decided here.
    other = fresh_file(db)
    key_other = flow.save("contributor", other)
    assert "another file" in db.refused(people["editor"], f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256) "
                                        f"values ({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', 'approved', '{key_other}', '{flow.brief_sha(key_other)}')")
    flow.decide("editor", lead, "approved", key, flow.brief_sha(key))


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_databases_canonical_json_gives_the_pages_sha256(db, tmp_path):
    """The page's own canon() (from app/src/page.js) on the template brief for every file's facts,
    with and without a reviewer note, an outcome for every synthetic case, and awkward strings: the
    database's SHA-256 of each draft must equal the page's."""
    note = {"id": "review-1", "kind": "returned", "at": "2026-10-22", "text": "Say which onward check carries the lead."}
    drafts = []
    for p in sorted(BRIEFS.glob("*.json")):
        if p.name != "index.json":
            c = json.loads(p.read_text(encoding="utf-8"))
            drafts += [{"id": f"brief:{c['slug']}", "draft": brief_for(c)}, {"id": f"brief:{c['slug']}:note", "draft": brief_for(c, [note])}]
    for case in json.loads((ROOT / "app" / "data" / "declarations" / "cases.json").read_text(encoding="utf-8"))["cases"]:
        drafts.append({"id": f"case:{case['id']}", "draft": outcome_for("case_" + case["id"])})
    awkward = [
        {"b": "1", "aa": [True, False, None, "x"], "a_b": {"z": "", "A": []}, "A": "upper", "Z": {}, "_": "under"},
        {"text": "quotes \" and \\ backslash / slash", "nl": "line\nnext\ttab\rcr\bback\fform", "ctl": "".join(map(chr, [1, 31, 127]))},
        {"money": "£8.0m and $1.1m", "accents": "caf" + chr(233) + " na" + chr(239) + "ve", "wide": chr(0x4E2D) + chr(0x6587), "pair": chr(0x1F600),
         "sep": chr(0x2028) + chr(0x2029), "amp": "<&>"},
        {"nested": [[[]], [{}], [{"k": ["v"]}]]},
    ]
    drafts += [{"id": f"awkward-{i}", "draft": d} for i, d in enumerate(awkward)]
    src = tmp_path / "drafts.json"
    src.write_text(json.dumps(drafts), encoding="utf-8")
    out = subprocess.run([NODE, str(ROOT / "tests" / "hosted_js_run.mjs"), "canon", str(ROOT), str(src)], capture_output=True, text=True, check=True)
    rows = json.loads(out.stdout)
    assert len([r for r in rows if r["id"].startswith("brief:")]) == 2 * 23
    assert len([r for r in rows if r["id"].startswith("case:")]) == 48
    got = db.sql(f"select x ->> 'id', private.draft_sha256(x -> 'draft'), private.canon_json(x -> 'draft') = x ->> 'canon' "
                 f"from jsonb_array_elements({lit(json.dumps(rows))}::jsonb) as x")
    want = {r["id"]: r["sha256"] for r in rows}
    assert len(got) == len(rows)
    for line in got:
        rid, h, same = line.split("|")
        assert (h, same) == (want[rid], "t"), rid


# ============================================================== insert-only

def test_nobody_updates_or_deletes_briefs_decisions_or_the_audit_log(db, people, flow):
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    flow.submit("contributor", lead, key)
    flow.decide("editor", lead, "approved", key, flow.brief_sha(key))
    db.as_(people["viewer"], f"insert into public.events (lead, run, action, detail) values ('{lead}', '{RUN}', 'pack_exported', 'data (.json)')")
    db.as_(None, f"insert into public.drafts (requested_by, lead, passed) values ('{people['contributor']}', '{lead}', true)", role="service_role")
    where = f"where lead = '{lead}'"
    stmts = {
        "briefs": [f"update public.briefs set draft = draft {where}", f"delete from public.briefs {where}"],
        "decisions": [f"update public.decisions set note = 'changed' {where}", f"delete from public.decisions {where}"],
        "audit": [f"update public.audit set detail = 'changed' {where}", f"delete from public.audit {where}"],
        "events": [f"update public.events set detail = 'changed' {where}", f"delete from public.events {where}"],
        "drafts": [f"update public.drafts set passed = false {where}", f"delete from public.drafts {where}"],
    }
    for table, qs in stmts.items():
        for q in qs:
            for who in ["contributor", "editor", "owner"]:
                msg = db.refused(people[who], q)
                assert "permission denied" in msg or "insert-only" in msg, (table, who, q, msg)
            # The service role (the function's key) and the dashboard are refused too.
            msg = db.refused(None, q, role="service_role")
            assert "permission denied" in msg or "insert-only" in msg, (table, q, msg)
            with pytest.raises(Refused, match="insert-only"):
                db.sql(q)
    for table in ["members", "briefs", "decisions", "files", "checks", "config", "events", "drafts", "audit"]:
        with pytest.raises(Refused, match="cannot be truncated"):
            db.sql(f"truncate public.{table} cascade")
        assert "permission denied" in db.refused(people["owner"], f"truncate public.{table}"), table
    assert db.one(f"select count(*) from public.briefs where lead = '{lead}'") == "1"
    assert db.one(f"select count(*) from public.decisions where lead = '{lead}'") == "1"


def test_people_cannot_write_the_audit_log_or_take_delete_or_truncate_rights(db, people):
    assert "permission denied" in db.refused(people["owner"], "insert into public.audit (actor_role, table_name, op, row_key, action, change) "
                                             "values ('authenticated', 'files', 'INSERT', 'x', 'brief_approved', '{}')")
    tables = ["members", "briefs", "decisions", "files", "checks", "config", "events", "drafts", "private_drafts", "audit"]
    for t in tables:
        for role in ["anon", "authenticated", "service_role"]:
            for priv in ["DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]:
                assert db.one(f"select has_table_privilege('{role}', 'public.{t}', '{priv}')") == "f", (t, role, priv)
        assert db.one(f"select has_table_privilege('anon', 'public.{t}', 'SELECT')") == "f", t
    for t in ["briefs", "decisions", "events", "drafts", "audit"]:
        assert db.one(f"select has_table_privilege('authenticated', 'public.{t}', 'UPDATE')") == "f", t
    # The function's key reads only what drafting needs, and writes only its own record.
    for t in ["files", "checks", "events", "private_drafts", "audit"]:
        assert db.one(f"select has_table_privilege('service_role', 'public.{t}', 'SELECT')") == "f", t
    for t in tables:
        want = "t" if t == "drafts" else "f"
        assert db.one(f"select has_table_privilege('service_role', 'public.{t}', 'INSERT')") == want, t


# ============================================================== the audit log

def test_every_action_leaves_an_audit_row_with_the_right_actor(db, people, flow):
    lead = fresh_file(db)
    ref = "DR-" + lead.replace("_", "-")
    start = db.one("select coalesce(max(id), 0) from public.audit")
    key = flow.save("contributor", lead)                                                   # brief_saved + pointer_set
    db.as_(people["contributor"], f"update public.files set assignee = '{people['contributor']}' where lead = '{lead}'")   # assigned
    db.as_(people["contributor"], f"insert into public.checks (lead, check_id, state) values ('{lead}', 'chpl-end-destination', 'done')")  # check_updated
    flow.submit("contributor", lead, key)                                                  # brief_submitted
    flow.decide("editor", lead, "returned", key, flow.brief_sha(key))                      # brief_returned
    key2 = flow.save("contributor2", lead)                                                 # brief_saved + pointer_set
    flow.submit("contributor2", lead, key2)                                                # brief_submitted
    flow.decide("editor2", lead, "approved", key2, flow.brief_sha(key2))                   # brief_approved
    db.as_(people["viewer"], f"insert into public.events (lead, run, action, detail) values ('{lead}', '{RUN}', 'pack_exported', 'evidence pack (.md)')")
    db.as_(people["viewer"], f"insert into public.events (run, action, detail) values ('{RUN}', 'exporter_screened', '61 rows, 4 destination and code pairs')")
    db.as_(None, f"insert into public.drafts (requested_by, lead, passed, rules, problem_count) values "
           f"('{people['contributor']}', '{lead}', false, '{{accusing_language,deny_list_name}}', 3)", role="service_role")   # draft_failed_screen
    db.as_(people["editor"], f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256) values "
           f"({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', 'reopened', '{key2}', '{flow.brief_sha(key2)}')")                   # reopened
    rows = [r.split("|") for r in db.sql(f"select action, actor, table_name, detail, coalesce(ref, ''), coalesce(run, ''), actor_role from public.audit "
                                          f"where id > {start} and (lead = '{lead}' or action = 'exporter_screened') order by id")]
    p = people
    want = [
        ("brief_saved", p["contributor"], "briefs", "version 1, from the template", ref, RUN),
        ("pointer_set", p["contributor"], "files", "drafting, version 1", ref, RUN),
        ("assigned", p["contributor"], "files", "", ref, RUN),
        ("check_updated", p["contributor"], "checks", "chpl-end-destination: checked", ref, ""),
        ("brief_submitted", p["contributor"], "files", "version 1", ref, RUN),
        ("brief_returned", p["editor"], "decisions", "with a note", ref, RUN),
        ("brief_saved", p["contributor2"], "briefs", "version 2, from the template", ref, RUN),
        ("pointer_set", p["contributor2"], "files", "drafting, version 2", ref, RUN),
        ("brief_submitted", p["contributor2"], "files", "version 2", ref, RUN),
        ("brief_approved", p["editor2"], "decisions", "four-eyes on", ref, RUN),
        ("pack_exported", p["viewer"], "events", "evidence pack (.md)", ref, RUN),
        ("exporter_screened", p["viewer"], "events", "61 rows, 4 destination and code pairs", "", RUN),
        ("draft_failed_screen", p["contributor"], "drafts", "3 problems: accusing_language, deny_list_name", ref, ""),
        ("reopened", p["editor"], "decisions", "", ref, RUN),
    ]
    assert [tuple(r[:6]) for r in rows] == want
    assert {r[6] for r in rows} == {"authenticated", "service_role"}
    # A change from the dashboard is logged too, with no person and the database role.
    db.sql(f"update public.members set display_name = 'Analyst viewer, renamed' where user_id = '{p['viewer']}'")
    last = db.one("select action || '|' || coalesce(actor::text, '') || '|' || actor_role || '|' || detail from public.audit order by id desc limit 1")
    assert last == "member_changed||database|name changed"
    # An update that changes nothing leaves no row.
    n = db.one("select count(*) from public.audit")
    db.as_(p["contributor"], f"update public.checks set state = 'done' where lead = '{lead}' and check_id = 'chpl-end-destination'")
    assert db.one("select count(*) from public.audit") == n


def test_the_audit_row_holds_the_change(db, people, flow):
    lead = fresh_file(db)
    flow.save("contributor", lead)
    db.as_(people["contributor"], f"insert into public.checks (lead, check_id, state) values ('{lead}', 'end-use-details', 'done')")
    db.as_(people["contributor2"], f"update public.checks set state = 'na' where lead = '{lead}' and check_id = 'end-use-details'")
    change = json.loads(db.one(f"select change from public.audit where lead = '{lead}' and table_name = 'checks' order by id desc limit 1"))
    assert change["old"]["state"] == "done" and change["new"]["state"] == "na"
    assert change["new"]["updated_by"] == people["contributor2"] and change["old"]["updated_by"] == people["contributor"]
    assert set(change["new"]) == {"state", "updated_by", "updated_at"}


# ============================================================== the workflow

def test_a_decision_needs_the_submitted_brief_once_per_submission(db, people, flow):
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    s = flow.brief_sha(key)
    ins = lambda decision: (f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256, note, reason) values "  # noqa: E731
                            f"({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', '{decision}', '{key}', '{s}', 'What needs to change.', "
                            f"{'null' if decision != 'rejected' else lit('data')})")
    assert "not the one submitted" in db.refused(people["editor"], ins("approved"))
    flow.submit("contributor", lead, key)
    flow.decide("editor", lead, "returned", key, s)
    assert "not been submitted again" in db.refused(people["editor"], ins("approved"))
    flow.submit("contributor", lead, key)
    flow.decide("editor", lead, "approved", key, s)
    assert "not been submitted again" in db.refused(people["editor2"], ins("rejected"))
    # A decided file is locked: no new brief and no pointer move until an Editor reopens it.
    with pytest.raises(Refused, match="reopen it first"):
        flow.save("contributor", lead)
    with pytest.raises(Refused, match="reopen it first"):
        flow.submit("contributor", lead, key)
    flow.decide("editor", lead, "reopened", key, s)
    assert "only an approved or rejected file can be reopened" in db.refused(
        people["editor"], f"insert into public.decisions (id, lead, run, series, decision) values ({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', 'reopened')")
    key2 = flow.save("contributor", lead)
    assert db.one(f"select version from public.briefs where key = '{key2}'") == "2"   # the refused save took no number
    # A brief of another file cannot be pointed at.
    other = fresh_file(db)
    key_other = flow.save("contributor", other)
    assert "another file" in db.refused(people["contributor"], f"update public.files set brief_id = '{key_other}' where lead = '{lead}'")


def test_rejections_need_their_reason_and_returns_their_note(db, people, flow):
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    flow.submit("contributor", lead, key)
    s = flow.brief_sha(key)
    dec = lambda decision, note, reason: (f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256, note, reason) values "  # noqa: E731
                                          f"({lit(new_id(lead))}, '{lead}', '{RUN}', 'x', '{decision}', '{key}', '{s}', {lit(note)}, {lit(reason) if reason else 'null'})")
    assert "needs a reason" in db.refused(people["editor"], dec("rejected", "No reason chosen.", None))
    assert "check constraint" in db.refused(people["editor"], dec("rejected", "", "tariff"))
    assert "check constraint" in db.refused(people["editor"], dec("returned", "  ", None))
    assert "only a rejection takes a reason" in db.refused(people["editor"], dec("returned", "What needs to change.", "data"))
    db.as_(people["editor"], dec("rejected", "", "duplicate"))
    assert db.one(f"select detail from public.audit where lead = '{lead}' and table_name = 'decisions'") == "Already covered by another file"
    assert "only a rejection takes a reason" in db.refused(people["editor"], dec("reopened", "", "data"))


def test_a_decided_file_locks_its_checks_until_reopened(db, people, flow):
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    check = f"insert into public.checks (lead, check_id, state) values ('{lead}', 'end-user-certificate', 'done') on conflict (lead, check_id) do update set state = excluded.state"
    db.as_(people["contributor"], check)
    flow.submit("contributor", lead, key)
    flow.decide("editor", lead, "rejected", key, flow.brief_sha(key))
    assert "decided" in db.refused(people["contributor"], check.replace("'done'", "'na'"))
    flow.decide("editor", lead, "reopened", key, flow.brief_sha(key))
    db.as_(people["contributor"], check.replace("'done'", "'na'"))
    flow.submit("contributor", lead, key)
    flow.decide("editor2", lead, "approved", key, flow.brief_sha(key))
    assert "decided" in db.refused(people["contributor"], check)
    assert db.one(f"select state from public.checks where lead = '{lead}'") == "na"


def test_the_pointers_time_moves_only_with_the_pointer(db, people, flow):
    """The page works out "returned" by comparing the pointer's time with the last decision's, so
    taking a file must not look like a new submission."""
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    flow.submit("contributor", lead, key)
    before = db.one(f"select updated_at from public.files where lead = '{lead}'")
    db.as_(people["contributor2"], f"update public.files set assignee = '{people['contributor2']}', updated_at = now() + interval '1 day' where lead = '{lead}'")
    assert db.one(f"select updated_at from public.files where lead = '{lead}'") == before
    assert db.one(f"select updated_by from public.files where lead = '{lead}'") == people["contributor"]
    # A person takes a file only for themselves.
    assert "only for themselves" in db.refused(people["contributor"], f"update public.files set assignee = '{people['viewer']}' where lead = '{lead}'")
    # A resubmission to the same brief moves the time, as the page's submit after a return does.
    db.as_(people["contributor"], f"update public.files set status = 'submitted', brief_id = '{key}' where lead = '{lead}'")
    assert db.one(f"select updated_at > '{before}' from public.files where lead = '{lead}'") == "t"


# ============================================================== the restricted layer

def test_a_case_outcome_goes_through_four_eyes_on_synthetic_ids_only(db, people, flow):
    case = fresh_case(db)
    key = flow.propose("contributor", case)
    assert db.one(f"select kind || '|' || version || '|' || coalesce(screen::text, 'none') from public.briefs where key = '{key}'") == "case_outcome|1|none"
    # The analyst who proposed it cannot approve it, even as an Editor; another Editor can.
    case2 = fresh_case(db)
    key2 = flow.propose("editor", case2)
    assert "four-eyes is on" in db.refused(people["editor"], f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256) values "
                                           f"({lit(new_id(case2))}, '{case2}', '{RUN}', 'x', 'approved', '{key2}', '{flow.brief_sha(key2)}')")
    flow.decide("editor2", case2, "approved", key2, flow.brief_sha(key2))
    # A rejection needs a note and takes no reason code.
    s = flow.brief_sha(key)
    rej = lambda note, reason: (f"insert into public.decisions (id, lead, run, series, decision, brief_id, brief_sha256, note, reason) values "  # noqa: E731
                                f"({lit(new_id(case))}, '{case}', '{RUN}', 'x', 'rejected', '{key}', '{s}', {lit(note)}, {lit(reason) if reason else 'null'})")
    assert "needs a note" in db.refused(people["editor"], rej("", None))
    assert "needs a note" in db.refused(people["editor"], rej("The outcome does not follow.", "other"))
    flow.decide("editor", case, "returned", key, s)
    key3 = flow.propose("contributor", case, "no_further_action")
    flow.decide("editor", case, "rejected", key3, flow.brief_sha(key3))
    flow.decide("editor2", case, "reopened", key3, flow.brief_sha(key3))
    rows = db.sql(f"select action || '|' || detail from public.audit where lead in ('{case}', '{case2}') and table_name in ('briefs', 'decisions', 'files') order by id")
    assert rows == ["case_outcome_proposed|Ask the exporter or its agent for more information", "case_outcome_submitted|version 1",
                    "case_outcome_proposed|Ask the exporter or its agent for more information", "case_outcome_submitted|version 1",
                    "case_outcome_approved|Ask the exporter or its agent for more information, four-eyes on",
                    "case_outcome_returned|with a note",
                    "case_outcome_proposed|No further action: an ordinary explanation was found", "case_outcome_submitted|version 2",
                    "case_outcome_rejected|with a note", "case_reopened|"]
    assert db.one(f"select distinct ref from public.audit where lead = '{case}'") == case[len("case_"):]
    # An outcome is for its own case, with one of the three outcomes and a note.
    c = people["contributor"]
    out = outcome_for(case)
    for bad in [dict(out, case_id="SYN-CASE-999"), dict(out, outcome="prosecute"), dict(out, note="  "), dict(out, note="x" * 601),
                dict(out, schema="radar-brief/1"), dict(out, extra="field")]:
        assert "outcome needs this case" in db.refused(c, insert_brief(case, bad, kind="case_outcome", source="analyst", series="EXP-0001 to Armenia")), bad
    assert "not a brief" in db.refused(c, insert_brief(case, out, kind="case_outcome", source="template", series="EXP-0001 to Armenia"))
    assert "a lead file takes a brief" in db.refused(c, insert_brief(fresh_file(db), out, kind="case_outcome", source="analyst", series="EXP-0001 to Armenia"))
    assert "no reviewer notes" in db.refused(c, insert_brief(case, out, kind="case_outcome", source="analyst", series="EXP-0001 to Armenia",
                                                              review=[{"id": "review-1", "kind": "returned", "text": "x"}]))


# ============================================================== roles

def test_a_viewer_reads_but_writes_nothing(db, people, flow, ctx):
    lead = fresh_file(db)
    flow.save("contributor", lead)
    v = people["viewer"]
    assert "needs a signed-in Contributor" in db.refused(v, insert_brief(lead, brief_for(ctx)))
    for q in [f"insert into public.checks (lead, check_id, state) values ('{lead}', 'chpl-end-destination', 'done')",
              f"insert into public.files (lead, assignee) values ('{fresh_file(db)}', '{v}')",
              "insert into public.config (key, four_eyes) values ('workflow', false) on conflict (key) do update set four_eyes = excluded.four_eyes"]:
        assert "row-level security" in db.refused(v, q), q
    # An update that row-level security does not let them make changes no row.
    db.as_(v, f"update public.files set status = 'submitted' where lead = '{lead}'")
    db.as_(v, "update public.config set four_eyes = false")
    assert db.one(f"select status from public.files where lead = '{lead}'") == "drafting"
    assert db.one("select four_eyes from public.config") == "t"
    assert db.one(f"select count(*) from public.briefs where lead = '{lead}'") == "1"


def test_only_the_owner_manages_members(db, people):
    new = str(uuid.uuid4())
    db.sql(f"insert into auth.users (id, email) values ('{new}', '{'@'.join(['new', 'workspace.test'])}')")
    assert "row-level security" in db.refused(people["editor"], f"insert into public.members (user_id, role) values ('{new}', 'viewer')")
    db.as_(people["owner"], f"insert into public.members (user_id, role, display_name) values ('{new}', 'viewer', 'Analyst new')")
    assert db.one(f"select invited_by from public.members where user_id = '{new}'") == people["owner"]
    db.as_(people["editor"], f"update public.members set role = 'owner' where user_id = '{people['editor']}'")   # RLS: no row changes
    assert db.one(f"select role from public.members where user_id = '{people['editor']}'") == "editor"
    assert "your own role" in db.refused(people["owner"], f"update public.members set role = 'viewer' where user_id = '{people['owner']}'")
    with pytest.raises(Refused, match="active owner"):
        db.sql(f"update public.members set active = false where user_id = '{people['owner']}'")
    db.as_(people["owner"], f"update public.members set role = 'contributor' where user_id = '{new}'")
    assert db.one(f"select detail from public.audit where table_name = 'members' and row_key = '{new}' order by id desc limit 1") == "role viewer to contributor"
    # A member's account cannot be deleted from under their records: access is removed with active.
    with pytest.raises(Refused, match="foreign key"):
        db.sql(f"delete from auth.users where id = '{people['contributor']}'")


def test_private_drafts_are_private(db, people):
    lead = fresh_file(db)
    db.as_(people["contributor"], f"insert into public.private_drafts (lead, working) values ('{lead}', '{{\"draft\": {{}}}}'::jsonb) "
           f"on conflict (user_id, lead) do update set working = excluded.working")
    assert db.as_(people["contributor"], f"select count(*) from public.private_drafts where lead = '{lead}'") == ["1"]
    for who in ["contributor2", "editor", "owner", "viewer"]:
        assert db.as_(people[who], f"select count(*) from public.private_drafts where lead = '{lead}'") == ["0"], who
    # Nobody can write a draft as someone else, and private drafts never reach the audit log.
    db.as_(people["editor"], f"insert into public.private_drafts (user_id, lead, working) values ('{people['contributor']}', '{lead}', null)")
    assert db.one(f"select count(*) from public.private_drafts where lead = '{lead}' and user_id = '{people['editor']}'") == "1"
    assert db.one("select count(*) from public.audit where table_name = 'private_drafts'") == "0"


def test_drafts_are_written_by_the_function_only_and_page_events_are_the_pages(db, people):
    lead = fresh_file(db)
    assert "permission denied" in db.refused(people["owner"], f"insert into public.drafts (requested_by, lead, passed) values ('{people['owner']}', '{lead}', true)")
    db.as_(None, f"insert into public.drafts (requested_by, lead, passed, rules, problem_count, draft_sha256) values "
           f"('{people['contributor']}', '{lead}', true, '{{}}', 0, '{'0' * 64}')", role="service_role")
    assert db.one(f"select action || '|' || actor || '|' || detail from public.audit where table_name = 'drafts' and lead = '{lead}'") \
        == f"draft_created|{people['contributor']}|by Claude, passed the screen"
    # Drafts are only for lead files: the restricted layer has no drafting.
    assert "check constraint" in db.refused(None, f"insert into public.drafts (requested_by, lead, passed) values ('{people['contributor']}', 'case_SYN-CASE-001', true)",
                                            role="service_role")
    # Page events: only the listed actions, and the actor is the caller.
    assert "check constraint" in db.refused(people["viewer"], "insert into public.events (action) values ('brief_approved')")
    assert "check constraint" in db.refused(people["viewer"], f"insert into public.events (action, detail) values ('audit_exported', {lit('x' * 201)})")
    assert "signed-in member" in db.refused(people["outsider"], "insert into public.events (action) values ('audit_exported')")


# ============================================================== follow-ups (phase 6)

def new_task_id() -> str:
    return f"task~{b36(int(time.time() * 1000))}~{''.join(random.choices('0123456789abcdefghijklmnopqrstuvwxyz', k=4))}"


def add_task(tid: str, lead: str, text: str = "Recheck after the next HMRC release", assignee: str | None = None) -> str:
    return (f"insert into public.tasks (id, lead, run, series, text, kind, due, assignee) values ({lit(tid)}, '{lead}', '{RUN}', 'x', {lit(text)}, "
            f"'release', '2026-11-12', {('%s' % lit(assignee)) if assignee else 'null'})")


def test_follow_ups_record_who_and_when_and_are_audited(db, people):
    lead, c, e, tid = fresh_file(db), people["contributor"], people["editor"], new_task_id()
    db.as_(c, add_task(tid, lead, assignee=c))
    assert db.sql(f"select created_by, done, coalesce(done_by::text, '-') from public.tasks where id = {lit(tid)}") == [f"{c}|f|-"]
    # Who added one is the caller; the page cannot say otherwise.
    assert "permission denied" in db.refused(c, f"insert into public.tasks (id, lead, text, created_by) values ({lit(new_task_id())}, '{lead}', 'x', '{e}')")
    db.as_(e, f"update public.tasks set done = true where id = {lit(tid)}")
    assert db.one(f"select done_by from public.tasks where id = {lit(tid)}") == e
    db.as_(c, f"update public.tasks set done = false where id = {lit(tid)}")
    assert db.one(f"select coalesce(done_by::text, '-') from public.tasks where id = {lit(tid)}") == "-"
    db.as_(c, f"update public.tasks set due = '2026-11-20' where id = {lit(tid)}")
    db.as_(c, f"update public.tasks set due = '2026-11-20' where id = {lit(tid)}")   # nothing changed: no entry
    rows = db.sql(f"select action || '|' || actor || '|' || detail from public.audit where table_name = 'tasks' and row_key = {lit(tid)} order by id")
    assert rows == [f"task_added|{c}|Recheck after the next HMRC release", f"task_done|{e}|Recheck after the next HMRC release",
                    f"task_reopened|{c}|Recheck after the next HMRC release", f"task_changed|{c}|Recheck after the next HMRC release (due date)"]


def test_a_follow_ups_owner_is_an_active_member_and_nobody_deletes_one(db, people):
    lead, c, tid = fresh_file(db), people["contributor"], new_task_id()
    assert "active member" in db.refused(c, add_task(tid, lead, assignee=people["removed"]))
    assert "active member" in db.refused(c, add_task(tid, lead, assignee=people["outsider"]))
    db.as_(c, add_task(tid, lead, text="Compare with the corridor's own import figures"))
    assert "permission denied" in db.refused(c, f"delete from public.tasks where id = {lit(tid)}")
    assert "permission denied" in db.refused(c, f"update public.tasks set lead = '{fresh_file(db)}' where id = {lit(tid)}")
    assert "permission denied" in db.refused(people["owner"], f"truncate public.tasks")


def test_a_viewer_reads_follow_ups_but_cannot_add_or_tick_them(db, people):
    lead, c, v, tid = fresh_file(db), people["contributor"], people["viewer"], new_task_id()
    db.as_(c, add_task(tid, lead))
    assert db.as_(v, f"select count(*) from public.tasks where id = {lit(tid)}") == ["1"]
    assert "row-level security" in db.refused(v, add_task(new_task_id(), lead))
    db.as_(v, f"update public.tasks set done = true where id = {lit(tid)}")   # changes no row
    assert db.one(f"select done from public.tasks where id = {lit(tid)}") == "f"
    assert db.as_(people["outsider"], f"select count(*) from public.tasks where id = {lit(tid)}") == ["0"]
    assert db.as_(people["removed"], f"select count(*) from public.tasks where id = {lit(tid)}") == ["0"]


def test_a_follow_up_whose_owner_left_can_still_be_ticked_off(db, people):
    lead, c, tid = fresh_file(db), people["contributor"], new_task_id()
    db.as_(c, add_task(tid, lead, assignee=people["contributor2"]))
    db.sql(f"update public.members set active = false where user_id = '{people['contributor2']}'")
    try:
        db.as_(c, f"update public.tasks set due = '2026-12-01' where id = {lit(tid)}")
        db.as_(c, f"update public.tasks set done = true where id = {lit(tid)}")
        assert db.one(f"select done from public.tasks where id = {lit(tid)}") == "t"
    finally:
        db.sql(f"update public.members set active = true where user_id = '{people['contributor2']}'")


# ============================================================== closing the loop (phase 6.5)

def decided(flow, db, decision: str = "approved") -> str:
    lead = fresh_file(db)
    key = flow.save("contributor", lead)
    flow.submit("contributor", lead, key)
    flow.decide("editor", lead, decision, key, flow.brief_sha(key))
    return lead


def add_outcome(lead: str, outcome: str, note: str = "") -> str:
    return f"insert into public.outcomes (lead, run, series, outcome, note) values ('{lead}', '{RUN}', 'x', '{outcome}', {lit(note)})"


def test_an_outcome_needs_a_decided_brief_and_records_who_and_when(db, people, flow):
    c, e = people["contributor"], people["editor"]
    undecided = fresh_file(db)
    flow.save("contributor", undecided)
    assert "once the brief is approved or rejected" in db.refused(c, add_outcome(undecided, "no_action"))
    lead = decided(flow, db)
    db.as_(c, add_outcome(lead, "referral", "Passed to the trade sanctions team."))
    assert db.one(f"select recorded_by from public.outcomes where lead = '{lead}'") == c
    assert "permission denied" in db.refused(c, f"insert into public.outcomes (lead, run, outcome, recorded_by) values ('{fresh_file(db)}', '{RUN}', 'watch', '{e}')")
    db.as_(e, f"update public.outcomes set outcome = 'outreach' where lead = '{lead}'")
    db.as_(e, f"update public.outcomes set outcome = 'outreach' where lead = '{lead}'")   # nothing changed: no entry
    rows = db.sql(f"select action || '|' || actor || '|' || detail from public.audit where table_name = 'outcomes' and row_key = '{lead}' order by id")
    assert rows == [f"outcome_recorded|{c}|Referred on: Passed to the trade sanctions team.", f"outcome_changed|{e}|Guidance or outreach to the trade: Passed to the trade sanctions team."]
    assert "permission denied" in db.refused(c, f"delete from public.outcomes where lead = '{lead}'")
    assert "row-level security" in db.refused(people["viewer"], add_outcome(decided(flow, db), "watch"))


def test_a_rejected_lead_can_only_be_closed_or_watched(db, people, flow):
    c = people["contributor"]
    lead = decided(flow, db, "rejected")
    assert "only be closed or kept on watch" in db.refused(c, add_outcome(lead, "referral"))
    db.as_(c, add_outcome(lead, "no_action"))
    assert "only be closed or kept on watch" in db.refused(c, f"update public.outcomes set outcome = 'enduse' where lead = '{lead}'")


def add_record(lead: str, rec: str, checks: list[str]) -> str:
    arr = "array[" + ", ".join(lit(x) for x in checks) + "]::text[]" if checks else "'{}'::text[]"
    return (f"insert into public.enduse_records (lead, run, series, reasons, checks, recommendation) values "
            f"('{lead}', '{RUN}', 'x', 'The rise holds over the months published.', {arr}, '{rec}')")


ALL_CHECKS = ["onward", "chpl", "display", "cases", "partners", "beyond"]


def test_an_end_use_record_needs_every_check_to_go_forward_and_a_second_editor(db, people, flow):
    c, e, e2 = people["contributor"], people["editor"], people["editor2"]
    lead = decided(flow, db)
    assert "put forward for an end-use controls decision" in db.refused(c, add_record(lead, "not_now", []))
    db.as_(c, add_outcome(lead, "enduse"))
    assert "enduse_forward_needs_every_check" in db.refused(c, add_record(lead, "forward", ALL_CHECKS[:-1]))
    db.as_(e, add_record(lead, "forward", ALL_CHECKS))
    assert db.one(f"select recorded_by || '|' || approved from public.enduse_records where lead = '{lead}'") == f"{e}|false"
    assert "cannot approve it" in db.refused(e, f"update public.enduse_records set approved = true where lead = '{lead}'")
    assert "only an editor" in db.refused(c, f"update public.enduse_records set approved = true where lead = '{lead}'")
    db.as_(e2, f"update public.enduse_records set approved = true where lead = '{lead}'")
    assert db.one(f"select approved_by from public.enduse_records where lead = '{lead}'") == e2
    assert "permission denied" in db.refused(e2, f"update public.enduse_records set approved_by = '{c}' where lead = '{lead}'")
    # New content is a new record: the approval goes.
    db.as_(c, f"update public.enduse_records set recommendation = 'not_now' where lead = '{lead}'")
    assert db.one(f"select recorded_by || '|' || approved || '|' || coalesce(approved_by::text, '-') from public.enduse_records where lead = '{lead}'") == f"{c}|false|-"
    acts = db.sql(f"select action || '|' || actor from public.audit where table_name = 'enduse_records' and row_key = '{lead}' order by id")
    assert acts == [f"enduse_recorded|{e}", f"enduse_approved|{e2}", f"enduse_recorded|{c}"]
    # Everyone who wrote it since the last approval is barred from approving it.
    db.as_(e, f"update public.enduse_records set reasons = 'The rise holds, and partner teams hold nothing on it.' where lead = '{lead}'")
    assert "cannot approve it" in db.refused(e, f"update public.enduse_records set approved = true where lead = '{lead}'")
    db.as_(e2, f"update public.enduse_records set approved = true where lead = '{lead}'")
    # A route put forward keeps its outcome until the record changes.
    db.as_(e, f"update public.enduse_records set recommendation = 'forward', checks = array['onward', 'chpl', 'display', 'cases', 'partners', 'beyond'] where lead = '{lead}'")
    assert "change the record first" in db.refused(c, f"update public.outcomes set outcome = 'watch' where lead = '{lead}'")


def test_a_referral_export_is_a_page_event(db, people):
    lead = fresh_file(db)
    db.as_(people["contributor"], f"insert into public.events (lead, run, action, detail) values ('{lead}', '{RUN}', 'referral_exported', 'OTSI')")
    assert db.one(f"select actor from public.events where lead = '{lead}' and action = 'referral_exported'") == people["contributor"]


# ============================================================== the monitor (phase 7)

def test_a_monitoring_decision_records_who_and_needs_a_grade_or_a_reason(db, people):
    c, e, item = people["contributor"], people["editor"], "mon-" + "".join(random.choices("0123456789abcdef", k=12))
    assert "monitor_accepted_has_a_grade" in db.refused(c, f"insert into public.monitor_decisions (item, decision) values ('{item}', 'accepted')")
    assert "monitor_rejected_has_a_reason" in db.refused(c, f"insert into public.monitor_decisions (item, decision, grade) values ('{item}', 'rejected', 'B2')")
    assert "check constraint" in db.refused(c, f"insert into public.monitor_decisions (item, decision, grade) values ('{item}', 'accepted', 'G7')")
    db.as_(c, f"insert into public.monitor_decisions (item, decision, grade) values ('{item}', 'accepted', 'B2')")
    assert db.one(f"select decided_by from public.monitor_decisions where item = '{item}'") == c
    db.as_(e, f"update public.monitor_decisions set decision = 'rejected', grade = null, reason = 'duplicate' where item = '{item}'")
    rows = db.sql(f"select action || '|' || actor || '|' || detail from public.audit where table_name = 'monitor_decisions' and row_key = '{item}' order by id")
    assert rows == [f"monitor_accepted|{c}|{item} accepted (B2)", f"monitor_changed|{e}|{item}: accepted (B2) to rejected (duplicate)"]
    change = db.one(f"select change::text from public.audit where table_name = 'monitor_decisions' and row_key = '{item}' and action = 'monitor_changed'")
    assert '"old"' in change and '"new"' in change
    assert "permission denied" in db.refused(c, f"delete from public.monitor_decisions where item = '{item}'")
    assert "row-level security" in db.refused(people["viewer"], f"insert into public.monitor_decisions (item, decision, grade) values ('mon-aaaaaaaaaaaa', 'accepted', 'A1')")
