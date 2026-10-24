-- The radar workspace's shared store on Supabase Postgres (London region).
--
-- A file is one corridor and one goods code at one run (aggregates, never an exporter), or a
-- case in the restricted layer, whose records are synthetic: every case is SYN-CASE-001 to
-- SYN-CASE-999, checked on every table. Outputs are leads for a person, never findings. A rise
-- in exports is a lead, not evidence of a breach.
--
-- File ids, as the page writes them (app/src/page.js, buildFiles and Decl.fileFor):
--   <run>_<corridor>-<code>    a lead or watch file, for example 2026-10_KZ-851762
--   case_SYN-CASE-<nnn>        a synthetic case in the restricted layer
--
-- What the database makes true, whatever a page or a script sends:
--   * Who and when: every author, actor and timestamp is set here, from auth.uid() and now().
--   * Roles (public.members): every active member reads; Contributors and up save briefs and
--     outcomes, move the status pointer and work the checks; only Editors and the owner record
--     decisions and change the four-eyes setting; only the owner manages members.
--   * Four-eyes: an approval is refused when four-eyes is on and the approver saved the brief,
--     or when the SHA-256 it names is not the brief's.
--   * Fingerprints: a brief or an outcome is refused unless its SHA-256 is the SHA-256 of its
--     draft written as the page's canonical JSON (keys sorted at every level).
--   * Reviewer notes: a brief lists the reviewer notes it was drafted against (at most five,
--     each {id, kind, at, text}), and its draft answers each of them once and no other. Which
--     notes are current is worked out by the page and the draft-brief function from the decisions.
--   * Workflow: a decision needs the brief that is submitted, once per submission; a decided
--     file is locked (no new brief, no pointer move, no check) until an Editor reopens it.
--   * Lessons: the hosted version has none yet, so a brief that carries one is refused.
--   * Insert-only: nobody, the dashboard included, changes or deletes briefs, decisions,
--     drafts, page events or the audit log, and no audited table can be truncated.
--   * The audit log is written here, by triggers, for every insert, update or delete of the
--     other tables. The page never writes it.
--
-- The page's records (app/README.md) map to these tables; app/src/hosted.js does the mapping:
--   members/{id}                    public.members
--   briefs/{id}/b/{brief}           public.briefs (author = id): brief versions and case outcomes
--   decisions/{id}/d/{decision}     public.decisions (author = id)
--   audit/{id}/e/{event}            public.audit (actor = id), written by triggers; the page's own
--                                   events (exports and the exporter screen) go to public.events
--   leads/{file}                    public.files: the status pointer and who has the file
--   checks/{file}                   public.checks, one row per question
--   config/workflow                 public.config
--   data/users/{id}/draft_{file}    public.private_drafts, readable by that person only
-- One table the page never writes: public.drafts (each Claude draft, written by the draft-brief
-- function). The private deny list is not in the database: it is bundled with the function.
--
-- Needs Supabase's auth schema (auth.users, auth.uid()) and roles (anon, authenticated,
-- service_role). tests/test_hosted_db.py runs this file on a local Postgres with a stand-in for
-- both (tests/hosted_supabase_stub.sql).

create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated, service_role;

-- ============================================================== tables

create table public.members (
  user_id uuid primary key references auth.users (id) on delete restrict,
  role text not null check (role in ('viewer', 'contributor', 'editor', 'owner')),
  display_name text not null default '' check (char_length(display_name) <= 80),
  active boolean not null default true,
  invited_at timestamptz not null default now(),
  invited_by uuid,
  updated_at timestamptz not null default now(),
  updated_by uuid
);
comment on table public.members is 'Who may use the workspace, at which role. Set active to false to remove access; records keep their author.';

create table public.briefs (
  id text primary key check (id ~ '^[A-Za-z0-9~_.-]{1,100}$'),
  author uuid not null references public.members (user_id),
  lead text not null check (lead ~ '^(?:[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}|case_SYN-CASE-[0-9]{3})$'),
  run text not null check (run ~ '^[0-9]{4}-[0-9]{2}$'),
  series text not null check (char_length(series) between 1 and 120),
  kind text not null default 'brief' check (kind in ('brief', 'case_outcome')),
  version integer not null,
  source text not null check (source in ('claude', 'template', 'edited', 'analyst')),
  draft jsonb not null check (jsonb_typeof(draft) = 'object' and octet_length(draft::text) <= 65536),
  review jsonb not null default '[]'::jsonb
    check (case when jsonb_typeof(review) = 'array' then jsonb_array_length(review) <= 5 and octet_length(review::text) <= 8192 else false end),
  lessons jsonb not null default '[]'::jsonb,
  screen jsonb check (screen is null or jsonb_typeof(screen) = 'object'),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  key text generated always as (author::text || '/' || id) stored unique
);
comment on table public.briefs is 'Each brief version (kind brief) and each proposed case outcome (kind case_outcome), screened by the page. Insert-only. key is the page''s brief id (author/id). review is the reviewer notes the brief answers.';
create index briefs_author on public.briefs (author, created_at);
create index briefs_lead on public.briefs (lead, version);

create table public.decisions (
  id text primary key check (id ~ '^[A-Za-z0-9~_.-]{1,100}$'),
  author uuid not null references public.members (user_id),
  lead text not null check (lead ~ '^(?:[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}|case_SYN-CASE-[0-9]{3})$'),
  run text not null check (run ~ '^[0-9]{4}-[0-9]{2}$'),
  series text not null check (char_length(series) between 1 and 120),
  decision text not null check (decision in ('approved', 'returned', 'rejected', 'reopened')),
  brief_id text references public.briefs (key),
  brief_sha256 text check (brief_sha256 ~ '^[0-9a-f]{64}$'),
  four_eyes boolean not null default true,
  note text not null default '' check (char_length(note) <= 1000),
  reason text check (reason in ('ordinary_trade', 'data', 'duplicate', 'other')),
  decided_at timestamptz not null default now(),
  check (decision <> 'returned' or btrim(note) <> '')
);
comment on table public.decisions is 'Each decision on a file: approved, returned, rejected or reopened. Insert-only.';
create index decisions_author on public.decisions (author, decided_at);
create index decisions_lead on public.decisions (lead, decided_at desc, id desc);

create table public.files (
  lead text primary key check (lead ~ '^(?:[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}|case_SYN-CASE-[0-9]{3})$'),
  run text check (run ~ '^[0-9]{4}-[0-9]{2}$'),
  series text check (char_length(series) between 1 and 120),
  status text check (status in ('drafting', 'submitted')),
  brief_id text references public.briefs (key),
  updated_at timestamptz,
  updated_by uuid,
  assignee uuid references public.members (user_id),
  assigned_at timestamptz,
  check (status is null or brief_id is not null)
);
comment on table public.files is 'The page''s leads/{file} record: the status pointer (drafting or submitted, and which brief) and who has the file. updated_at moves only with the pointer.';

create table public.checks (
  lead text not null check (lead ~ '^(?:[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}|case_SYN-CASE-[0-9]{3})$'),
  check_id text not null check (check_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$'),
  state text not null check (state in ('open', 'done', 'na')),
  updated_by uuid,
  updated_at timestamptz not null default now(),
  primary key (lead, check_id)
);
comment on table public.checks is 'Each question''s state on a file: open, done (checked) or na (not applicable), with who and when.';

create table public.config (
  key text primary key check (key = 'workflow'),
  four_eyes boolean not null default true,
  updated_at timestamptz not null default now(),
  updated_by uuid
);
comment on table public.config is 'The approval setting. Four-eyes is on unless an Editor turns it off.';

create table public.events (
  id bigint generated always as identity primary key,
  actor uuid not null references public.members (user_id),
  lead text check (lead ~ '^(?:[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}|case_SYN-CASE-[0-9]{3})$'),
  run text check (run ~ '^[0-9]{4}-[0-9]{2}$'),
  action text not null check (action in ('pack_exported', 'audit_exported', 'exporter_screened', 'exporter_exported')),
  detail text not null default '' check (char_length(detail) <= 200),
  at timestamptz not null default now()
);
comment on table public.events is 'What the page did that changes no table (an export, a shipments file screened in the browser). The database sets who and when; the page says what, never the file''s name or contents. Insert-only.';

create table public.drafts (
  id bigint generated always as identity primary key,
  requested_by uuid not null references public.members (user_id),
  lead text not null check (lead ~ '^[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}$'),
  passed boolean not null,
  rules text[] not null default '{}' check (cardinality(rules) <= 40),
  problem_count integer not null default 0 check (problem_count >= 0),
  prompt_sha256 text check (prompt_sha256 ~ '^[0-9a-f]{64}$'),
  draft_sha256 text check (draft_sha256 ~ '^[0-9a-f]{64}$'),
  model text check (char_length(model) <= 80),
  stop_reason text check (char_length(stop_reason) <= 40),
  input_tokens integer,
  output_tokens integer,
  rules_version text check (char_length(rules_version) <= 40),
  at timestamptz not null default now()
);
comment on table public.drafts is 'Each draft the draft-brief function asked Claude for: who, which file, whether it passed the screen and which rules it broke. Never the text. Insert-only.';
create index drafts_requested_by on public.drafts (requested_by, at);

create table public.private_drafts (
  user_id uuid not null default auth.uid() references public.members (user_id),
  lead text not null check (lead ~ '^(?:[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}|case_SYN-CASE-[0-9]{3})$'),
  working jsonb check (working is null or (jsonb_typeof(working) = 'object' and octet_length(working::text) <= 131072)),
  at timestamptz not null default now(),
  primary key (user_id, lead)
);
comment on table public.private_drafts is 'A person''s unsaved, screened draft. Only that person can read it. Not audited, so the shared log never holds it.';

create table public.audit (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  actor uuid,
  actor_role text not null,
  table_name text not null,
  op text not null check (op in ('INSERT', 'UPDATE', 'DELETE')),
  row_key text not null,
  lead text,
  ref text,
  run text,
  action text not null,
  detail text not null default '',
  change jsonb not null
);
comment on table public.audit is 'Written by triggers only. actor is null for a change made from the dashboard or a migration; actor_role says which database role made it. Insert-only.';
create index audit_actor on public.audit (actor, at desc, id desc);
create index audit_lead on public.audit (lead, at);

-- ============================================================== helpers

create function private.role_rank(r text) returns integer
language sql immutable set search_path = '' as $$
  select case r when 'viewer' then 1 when 'contributor' then 2 when 'editor' then 3 when 'owner' then 4 else 0 end
$$;

-- The caller's role, or null when they are not an active member.
create function private.my_role() returns text
language sql stable security definer set search_path = '' as $$
  select m.role from public.members m where m.user_id = auth.uid() and m.active
$$;

create function private.at_least(r text) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce(private.role_rank(private.my_role()) >= private.role_rank(r), false)
$$;

create function private.is_case(lead text) returns boolean
language sql immutable set search_path = '' as $$
  select coalesce(lead ~ '^case_SYN-CASE-[0-9]{3}$', false)
$$;

-- The file's reference as the page shows it: DR-<run>-<corridor>-<code>, or the case id.
create function private.file_ref(lead text) returns text
language sql immutable set search_path = '' as $$
  select case when lead is null then null when lead ~ '^case_' then substr(lead, 6) else 'DR-' || replace(lead, '_', '-') end
$$;

-- The page's canonical JSON (app/src/page.js, canon): keys sorted at every level, no spaces,
-- strings escaped as JSON.stringify does. The same text as the page for strings, booleans, null,
-- arrays, objects with ASCII keys and plain decimal numbers; drafts hold no numbers.
create function private.canon_json(v jsonb) returns text
language plpgsql immutable strict set search_path = '' as $$
declare
  t text := jsonb_typeof(v);
  out_text text;
begin
  if t = 'object' then
    select '{' || coalesce(string_agg(to_json(e.key)::text || ':' || private.canon_json(e.value), ',' order by e.key collate "C"), '') || '}'
      into out_text from jsonb_each(v) as e;
    return out_text;
  elsif t = 'array' then
    select '[' || coalesce(string_agg(private.canon_json(e.value), ',' order by e.ord), '') || ']'
      into out_text from jsonb_array_elements(v) with ordinality as e(value, ord);
    return out_text;
  elsif t = 'string' then
    return to_json(v #>> '{}')::text;
  end if;
  return v::text;
end $$;

create function private.draft_sha256(d jsonb) returns text
language sql immutable strict set search_path = '' as $$
  select encode(sha256(convert_to(private.canon_json(d), 'UTF8')), 'hex')
$$;

-- Serialises changes to one file's workflow (briefs, the pointer, decisions, checks), so two
-- people acting at once cannot both pass a check that each would fail.
create function private.lock_file(lead text) returns void
language plpgsql volatile set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(hashtextextended('diversion-radar-workspace:' || lead, 0));
end $$;

create function private.last_decision(lead_id text) returns text
language sql stable security definer set search_path = '' as $$
  select d.decision from public.decisions d where d.lead = lead_id order by d.decided_at desc, d.id desc limit 1
$$;

create function private.refuse(msg text, code text default '23514') returns void
language plpgsql set search_path = '' as $$
begin
  raise exception using errcode = code, message = msg;
end $$;

-- Words the page uses for these, so an entry reads the same in the hosted log as in the pilot's.
create function private.source_label(s text) returns text
language sql immutable set search_path = '' as $$
  select case s when 'claude' then 'drafted by Claude' when 'template' then 'from the template' when 'edited' then 'edited' else coalesce(s, '') end
$$;

create function private.outcome_label(o text) returns text
language sql immutable set search_path = '' as $$
  select case o when 'refer' then 'Refer for investigation' when 'more_information' then 'Ask the exporter or its agent for more information'
                when 'no_further_action' then 'No further action: an ordinary explanation was found' else coalesce(o, '') end
$$;

create function private.reject_label(r text) returns text
language sql immutable set search_path = '' as $$
  select case r when 'ordinary_trade' then 'Ordinary trade explains the rise' when 'data' then 'A data problem or revision'
                when 'duplicate' then 'Already covered by another file' when 'other' then 'Other (see the note)' else '' end
$$;

-- ============================================================== before triggers: who, when, rules

create function private.members_before() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
begin
  if tg_op = 'INSERT' then
    new.invited_at := now();
    new.invited_by := uid;
  else
    if new.user_id <> old.user_id then perform private.refuse('a member''s id cannot change'); end if;
    new.invited_at := old.invited_at;
    new.invited_by := old.invited_by;
    if uid is not null and new.user_id = uid and (new.role <> old.role or new.active <> old.active) then
      perform private.refuse('you cannot change your own role or access', '42501');
    end if;
    if old.role = 'owner' and old.active and (new.role <> 'owner' or not new.active)
       and not exists (select 1 from public.members m where m.role = 'owner' and m.active and m.user_id <> new.user_id) then
      perform private.refuse('the workspace needs an active owner');
    end if;
    if (new.role, new.display_name, new.active) is not distinct from (old.role, old.display_name, old.active) then
      new.updated_at := old.updated_at;   -- nothing changed, so nothing happened
      new.updated_by := old.updated_by;
      return new;
    end if;
  end if;
  new.updated_at := now();
  new.updated_by := uid;
  return new;
end $$;

create function private.briefs_before() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null or not private.at_least('contributor') then
    perform private.refuse('saving a brief or an outcome needs a signed-in Contributor, Editor or owner', '42501');
  end if;
  new.author := uid;
  perform private.lock_file(new.lead);
  if private.last_decision(new.lead) in ('approved', 'rejected') then
    perform private.refuse('the file is decided; an Editor must reopen it first');
  end if;
  new.created_at := now();
  new.version := coalesce((select max(b.version) from public.briefs b where b.lead = new.lead), 0) + 1;
  if new.lessons is distinct from '[]'::jsonb then
    perform private.refuse('the hosted version has no lessons yet, so a brief cannot carry one');
  end if;
  if new.sha256 is distinct from private.draft_sha256(new.draft) then
    perform private.refuse('the SHA-256 does not match the draft');
  end if;

  if private.is_case(new.lead) then
    -- A proposed outcome on a synthetic case (app/src/page.js, Decl.propose).
    if new.kind is distinct from 'case_outcome' or new.source is distinct from 'analyst' then
      perform private.refuse('a case file takes an outcome proposed by an analyst, not a brief');
    end if;
    if new.draft ->> 'schema' is distinct from 'radar-case-outcome/1' or new.draft -> 'case_id' is distinct from to_jsonb(substr(new.lead, 6))
       or coalesce(new.draft ->> 'outcome', '') not in ('refer', 'more_information', 'no_further_action')
       or jsonb_typeof(new.draft -> 'note') is distinct from 'string' or btrim(new.draft ->> 'note') = '' or char_length(new.draft ->> 'note') > 600
       or (select count(*) from jsonb_object_keys(new.draft)) <> 4 then
      perform private.refuse('an outcome needs this case''s id, one of the three outcomes and a note of at most 600 characters');
    end if;
    if new.review is distinct from '[]'::jsonb then
      perform private.refuse('an outcome answers no reviewer notes');
    end if;
    new.screen := null;
    return new;
  end if;

  -- A brief version on a lead or watch file (app/src/page.js, Brief.saveDraft).
  if new.kind is distinct from 'brief' or new.source not in ('claude', 'template', 'edited') then
    perform private.refuse('a lead file takes a brief drafted by Claude, from the template or edited');
  end if;
  if split_part(new.lead, '_', 1) is distinct from new.run then
    perform private.refuse('the brief''s run is not the file''s run');
  end if;
  if new.draft ->> 'schema' is distinct from 'radar-brief/1' or new.draft -> 'series' is distinct from to_jsonb(new.series)
     or new.draft -> 'run' is distinct from to_jsonb(new.run) then
    perform private.refuse('the brief is not a radar-brief/1 draft for this file''s series and run');
  end if;
  if jsonb_typeof(new.review) is distinct from 'array' then
    perform private.refuse('a brief''s reviewer notes must be a list');
  end if;
  if exists (select 1 from jsonb_array_elements(new.review) e
             where jsonb_typeof(e) <> 'object' or coalesce(e ->> 'id', '') !~ '^review-[1-5]$'
                or coalesce(e ->> 'kind', '') not in ('returned', 'rejected') or jsonb_typeof(e -> 'text') is distinct from 'string'
                or (e ? 'at' and jsonb_typeof(e -> 'at') is distinct from 'string'))
     or (select count(distinct e ->> 'id') from jsonb_array_elements(new.review) e) <> jsonb_array_length(new.review) then
    perform private.refuse('each reviewer note needs its own id, review-1 to review-5, a kind and a text');
  end if;
  if (select coalesce(array_agg(e ->> 'id' order by e ->> 'id'), '{}') from jsonb_array_elements(new.review) e)
     is distinct from (select coalesce(array_agg(a ->> 'note' order by a ->> 'note'), '{}')
                       from jsonb_array_elements(case when jsonb_typeof(new.draft -> 'responds_to_review') = 'array'
                                                      then new.draft -> 'responds_to_review' else '[]'::jsonb end) a) then
    perform private.refuse('the brief must answer each reviewer note it lists, once, and no other');
  end if;
  if new.screen -> 'ok' is distinct from 'true'::jsonb or jsonb_typeof(new.screen -> 'rules') is distinct from 'string'
     or char_length(new.screen ->> 'rules') > 40 then
    perform private.refuse('a brief must have passed the screen');
  end if;
  new.screen := jsonb_build_object('ok', true, 'rules', new.screen -> 'rules', 'checked_at', to_jsonb(now()));
  return new;
end $$;

create function private.decisions_before() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  b_row public.briefs;
  f_row public.files;
  last_decision text;
  last_at timestamptz;
begin
  if uid is null or not private.at_least('editor') then
    perform private.refuse('only an Editor or the owner can record a decision', '42501');
  end if;
  if new.decision is null or new.decision not in ('approved', 'returned', 'rejected', 'reopened') then
    perform private.refuse('a decision approves, returns, rejects or reopens a file; the hosted version has no lessons yet');
  end if;
  if new.decision <> 'rejected' and new.reason is not null then
    perform private.refuse('only a rejection takes a reason');
  end if;
  new.author := uid;
  perform private.lock_file(new.lead);
  new.decided_at := now();
  new.four_eyes := coalesce((select c.four_eyes from public.config c where c.key = 'workflow'), true);
  if not private.is_case(new.lead) and split_part(new.lead, '_', 1) is distinct from new.run then
    perform private.refuse('the decision''s run is not the file''s run');
  end if;
  if new.brief_id is not null then
    select * into b_row from public.briefs b where b.key = new.brief_id;
    if not found or b_row.lead <> new.lead then
      perform private.refuse('the decision names a brief of another file');
    end if;
    if new.brief_sha256 is distinct from b_row.sha256 then
      perform private.refuse('the SHA-256 does not match the brief''s');
    end if;
  end if;
  select d.decision, d.decided_at into last_decision, last_at
    from public.decisions d where d.lead = new.lead order by d.decided_at desc, d.id desc limit 1;
  if new.decision = 'reopened' then
    if last_decision is null or last_decision not in ('approved', 'rejected') then
      perform private.refuse('only an approved or rejected file can be reopened');
    end if;
    return new;
  end if;
  if new.brief_id is null then
    perform private.refuse('the decision must name the brief it is about');
  end if;
  if new.decision = 'rejected' then
    if private.is_case(new.lead) and (btrim(new.note) = '' or new.reason is not null) then
      perform private.refuse('rejecting an outcome needs a note and no reason code');
    elsif not private.is_case(new.lead) and new.reason is null then
      perform private.refuse('rejecting a lead needs a reason');
    end if;
  end if;
  if new.decision = 'approved' and new.four_eyes and b_row.author = uid then
    perform private.refuse('four-eyes is on: the person who saved this brief cannot approve it');
  end if;
  select * into f_row from public.files f where f.lead = new.lead;
  if not found or f_row.status is distinct from 'submitted' or f_row.brief_id is distinct from new.brief_id then
    perform private.refuse('this brief is not the one submitted for approval');
  end if;
  if last_decision in ('approved', 'rejected') or (last_at is not null and f_row.updated_at <= last_at) then
    perform private.refuse('the file has not been submitted again since the last decision');
  end if;
  return new;
end $$;

-- updated_at and updated_by belong to the status pointer: they move when a request sets the
-- status or the brief (files_pointer below), even to the same values, as a resubmission after a
-- return does, and never when someone only takes or releases the file. The page works out a
-- returned brief by comparing the pointer's time with the last decision's.
create function private.files_before() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
  b_lead text;
begin
  if tg_op = 'UPDATE' and new.lead <> old.lead then perform private.refuse('a file''s id cannot change'); end if;
  perform private.lock_file(new.lead);
  if new.brief_id is not null then
    select b.lead into b_lead from public.briefs b where b.key = new.brief_id;
    if b_lead is distinct from new.lead then perform private.refuse('the pointer names a brief of another file'); end if;
  end if;
  if new.run is not null and not private.is_case(new.lead) and split_part(new.lead, '_', 1) is distinct from new.run then
    perform private.refuse('the pointer''s run is not the file''s run');
  end if;
  if tg_op = 'UPDATE' then
    new.updated_at := old.updated_at;
    new.updated_by := old.updated_by;
  elsif new.status is not null or new.brief_id is not null then
    if private.last_decision(new.lead) in ('approved', 'rejected') then
      perform private.refuse('the file is decided; an Editor must reopen it first');
    end if;
    new.updated_at := now();
    new.updated_by := uid;
  else
    new.updated_at := null;
    new.updated_by := null;
  end if;
  if (tg_op = 'INSERT' and new.assignee is not null) or (tg_op = 'UPDATE' and new.assignee is distinct from old.assignee) then
    if new.assignee is not null and uid is not null and new.assignee <> uid then
      perform private.refuse('a person can take a file only for themselves', '42501');
    end if;
    new.assigned_at := case when new.assignee is not null then now() end;
  elsif tg_op = 'UPDATE' then
    new.assigned_at := old.assigned_at;
  else
    new.assigned_at := null;
  end if;
  return new;
end $$;

-- Runs after files_before (triggers of one kind fire in name order), only when the request sets
-- the status or the brief.
create function private.files_pointer() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if private.last_decision(new.lead) in ('approved', 'rejected') then
    perform private.refuse('the file is decided; an Editor must reopen it first');
  end if;
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end $$;

create function private.checks_before() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' and (new.lead <> old.lead or new.check_id <> old.check_id) then
    perform private.refuse('a check''s file and id cannot change');
  end if;
  perform private.lock_file(new.lead);
  if private.last_decision(new.lead) in ('approved', 'rejected') then
    perform private.refuse('the file is decided; an Editor must reopen it before the checks change');
  end if;
  if tg_op = 'UPDATE' and new.state = old.state then
    new.updated_by := old.updated_by;   -- nothing changed, so nothing happened
    new.updated_at := old.updated_at;
    return new;
  end if;
  new.updated_by := auth.uid();
  new.updated_at := now();
  return new;
end $$;

create function private.config_before() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' and new.key <> old.key then perform private.refuse('a setting''s key cannot change'); end if;
  if tg_op = 'UPDATE' and new.four_eyes = old.four_eyes then
    new.updated_at := old.updated_at;   -- nothing changed, so nothing happened
    new.updated_by := old.updated_by;
    return new;
  end if;
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end $$;

create function private.events_before() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null or private.my_role() is null then perform private.refuse('an event needs a signed-in member', '42501'); end if;
  new.actor := uid;
  new.at := now();
  return new;
end $$;

create function private.drafts_before() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is not null then new.requested_by := auth.uid(); end if;
  new.at := now();
  return new;
end $$;

create function private.private_drafts_before() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then perform private.refuse('a private draft needs a signed-in member', '42501'); end if;
  if tg_op = 'UPDATE' and new.lead <> old.lead then perform private.refuse('a draft''s file cannot change'); end if;
  new.user_id := uid;
  new.at := now();
  return new;
end $$;

create trigger members_before before insert or update on public.members for each row execute function private.members_before();
create trigger briefs_before before insert on public.briefs for each row execute function private.briefs_before();
create trigger decisions_before before insert on public.decisions for each row execute function private.decisions_before();
create trigger files_a_before before insert or update on public.files for each row execute function private.files_before();
create trigger files_b_pointer before update of status, brief_id on public.files for each row execute function private.files_pointer();
create trigger checks_before before insert or update on public.checks for each row execute function private.checks_before();
create trigger config_before before insert or update on public.config for each row execute function private.config_before();
create trigger events_before before insert on public.events for each row execute function private.events_before();
create trigger drafts_before before insert on public.drafts for each row execute function private.drafts_before();
create trigger private_drafts_before before insert or update on public.private_drafts for each row execute function private.private_drafts_before();

-- ============================================================== insert-only and no truncate

create function private.refuse_change() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception using errcode = '42501', message = format('%s is insert-only: %s is refused', tg_table_name, lower(tg_op));
end $$;

create trigger briefs_insert_only before update or delete on public.briefs for each row execute function private.refuse_change();
create trigger decisions_insert_only before update or delete on public.decisions for each row execute function private.refuse_change();
create trigger events_insert_only before update or delete on public.events for each row execute function private.refuse_change();
create trigger drafts_insert_only before update or delete on public.drafts for each row execute function private.refuse_change();
create trigger audit_insert_only before update or delete on public.audit for each row execute function private.refuse_change();

create function private.refuse_truncate() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception using errcode = '42501', message = format('%s cannot be truncated: the audit log would lose track of it', tg_table_name);
end $$;

create trigger members_no_truncate before truncate on public.members for each statement execute function private.refuse_truncate();
create trigger briefs_no_truncate before truncate on public.briefs for each statement execute function private.refuse_truncate();
create trigger decisions_no_truncate before truncate on public.decisions for each statement execute function private.refuse_truncate();
create trigger files_no_truncate before truncate on public.files for each statement execute function private.refuse_truncate();
create trigger checks_no_truncate before truncate on public.checks for each statement execute function private.refuse_truncate();
create trigger config_no_truncate before truncate on public.config for each statement execute function private.refuse_truncate();
create trigger events_no_truncate before truncate on public.events for each statement execute function private.refuse_truncate();
create trigger drafts_no_truncate before truncate on public.drafts for each statement execute function private.refuse_truncate();
create trigger audit_no_truncate before truncate on public.audit for each statement execute function private.refuse_truncate();

-- ============================================================== the audit log

create function private.brief_version(brief_key text) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((select b.version::text from public.briefs b where b.key = brief_key), '?')
$$;

create function private.brief_outcome(brief_key text) returns text
language sql stable security definer set search_path = '' as $$
  select (select b.draft ->> 'outcome' from public.briefs b where b.key = brief_key)
$$;

create function private.audit_row() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  n jsonb := case when tg_op <> 'DELETE' then to_jsonb(new) end;
  o jsonb := case when tg_op <> 'INSERT' then to_jsonb(old) end;
  r jsonb;
  diff_new jsonb := '{}'::jsonb;
  diff_old jsonb := '{}'::jsonb;
  act text;
  det text := '';
  file_id text;
  run_id text;
  who uuid := auth.uid();
  rk text;
  claims jsonb;
  is_case boolean;
  bits text[] := '{}';
begin
  r := coalesce(n, o);
  file_id := r ->> 'lead';
  run_id := r ->> 'run';
  is_case := private.is_case(file_id);
  if tg_op = 'UPDATE' then
    select coalesce(jsonb_object_agg(k, n -> k), '{}'::jsonb), coalesce(jsonb_object_agg(k, o -> k), '{}'::jsonb)
      into diff_new, diff_old
      from jsonb_object_keys(n) as k where n -> k is distinct from o -> k;
    if diff_new = '{}'::jsonb then return null; end if;   -- nothing changed, so nothing happened
  end if;
  begin
    claims := nullif(current_setting('request.jwt.claims', true), '')::jsonb;
  exception when others then
    claims := null;
  end;

  case tg_table_name
  when 'members' then
    rk := r ->> 'user_id';
    if tg_op = 'INSERT' then act := 'member_added'; det := r ->> 'role';
    elsif tg_op = 'UPDATE' then
      act := 'member_changed';
      if diff_new ? 'role' then bits := bits || format('role %s to %s', o ->> 'role', n ->> 'role'); end if;
      if diff_new ? 'active' then bits := bits || (case when (n ->> 'active')::boolean then 'access restored' else 'access removed' end); end if;
      if diff_new ? 'display_name' then bits := bits || 'name changed'::text; end if;
      det := array_to_string(bits, ', ');
    end if;
  when 'briefs' then
    rk := r ->> 'key';
    if r ->> 'kind' = 'case_outcome' then
      act := 'case_outcome_proposed';
      det := private.outcome_label(r -> 'draft' ->> 'outcome');
    else
      act := 'brief_saved';
      det := format('version %s, %s', r ->> 'version', private.source_label(r ->> 'source'));
    end if;
  when 'decisions' then
    rk := (r ->> 'author') || '/' || (r ->> 'id');
    if is_case then
      act := case r ->> 'decision' when 'approved' then 'case_outcome_approved' when 'returned' then 'case_outcome_returned'
                                   when 'rejected' then 'case_outcome_rejected' else 'case_reopened' end;
      det := case r ->> 'decision'
        when 'approved' then format('%s, four-eyes %s', private.outcome_label(private.brief_outcome(r ->> 'brief_id')),
                                    case when (r ->> 'four_eyes')::boolean then 'on' else 'off' end)
        when 'returned' then 'with a note' when 'rejected' then 'with a note' else '' end;
    else
      act := case r ->> 'decision' when 'approved' then 'brief_approved' when 'returned' then 'brief_returned'
                                   when 'rejected' then 'brief_rejected' else 'reopened' end;
      det := case r ->> 'decision'
        when 'approved' then format('four-eyes %s', case when (r ->> 'four_eyes')::boolean then 'on' else 'off' end)
        when 'returned' then 'with a note'
        when 'rejected' then private.reject_label(r ->> 'reason')
        else '' end;
    end if;
  when 'files' then
    rk := r ->> 'lead';
    if tg_op <> 'DELETE' then
      -- The pointer was set when its time moved (files_pointer), so a resubmission counts.
      if (tg_op = 'INSERT' and (n ->> 'status' is not null or n ->> 'brief_id' is not null))
         or diff_new ? 'updated_at' or diff_new ? 'status' or diff_new ? 'brief_id' then
        if n ->> 'status' = 'submitted' then
          act := case when is_case then 'case_outcome_submitted' else 'brief_submitted' end;
          det := format('version %s', private.brief_version(n ->> 'brief_id'));
        else
          act := 'pointer_set';
          det := format('%s, version %s', coalesce(n ->> 'status', 'no status'), private.brief_version(n ->> 'brief_id'));
        end if;
        if (tg_op = 'INSERT' and n ->> 'assignee' is not null) or diff_new ? 'assignee' then det := det || '; assignee changed'; end if;
      elsif (tg_op = 'INSERT' and n ->> 'assignee' is not null) or diff_new ? 'assignee' then
        act := case when n ->> 'assignee' is not null then 'assigned' else 'unassigned' end;
      else
        act := 'file_updated';
      end if;
    end if;
  when 'checks' then
    rk := (r ->> 'lead') || '/' || (r ->> 'check_id');
    if tg_op <> 'DELETE' then
      act := 'check_updated';
      det := format('%s: %s', n ->> 'check_id', case n ->> 'state' when 'done' then 'checked' when 'na' then 'not applicable' else 'open' end);
    end if;
  when 'config' then
    rk := r ->> 'key';
    if tg_op <> 'DELETE' then
      act := 'workflow_changed';
      det := case when (n ->> 'four_eyes')::boolean then 'four-eyes on' else 'four-eyes off' end;
    end if;
  when 'events' then
    rk := r ->> 'id';
    act := r ->> 'action';
    det := r ->> 'detail';
    who := (r ->> 'actor')::uuid;
  when 'drafts' then
    rk := r ->> 'id';
    who := (r ->> 'requested_by')::uuid;
    if (r ->> 'passed')::boolean then
      act := 'draft_created';
      det := 'by Claude, passed the screen';
    else
      act := 'draft_failed_screen';
      det := format('%s %s: %s', r ->> 'problem_count', case when (r ->> 'problem_count')::int = 1 then 'problem' else 'problems' end,
                    array_to_string(array(select jsonb_array_elements_text(r -> 'rules')), ', '));
    end if;
  else
    rk := coalesce(r ->> 'id', '');
  end case;

  if tg_op = 'DELETE' then
    act := 'row_deleted';
    det := tg_table_name;
  end if;

  insert into public.audit (at, actor, actor_role, table_name, op, row_key, lead, ref, run, action, detail, change)
  values (now(), who, coalesce(claims ->> 'role', 'database'), tg_table_name, tg_op, coalesce(rk, ''), file_id, private.file_ref(file_id), run_id,
          coalesce(act, 'row_changed'), coalesce(det, ''),
          case tg_op when 'INSERT' then jsonb_build_object('new', n) when 'DELETE' then jsonb_build_object('old', o)
                     else jsonb_build_object('old', diff_old, 'new', diff_new) end);
  return null;
end $$;

create trigger members_audit after insert or update or delete on public.members for each row execute function private.audit_row();
create trigger briefs_audit after insert on public.briefs for each row execute function private.audit_row();
create trigger decisions_audit after insert on public.decisions for each row execute function private.audit_row();
create trigger files_audit after insert or update or delete on public.files for each row execute function private.audit_row();
create trigger checks_audit after insert or update or delete on public.checks for each row execute function private.audit_row();
create trigger config_audit after insert or update or delete on public.config for each row execute function private.audit_row();
create trigger events_audit after insert on public.events for each row execute function private.audit_row();
create trigger drafts_audit after insert on public.drafts for each row execute function private.audit_row();

-- ============================================================== privileges and row-level security

-- Supabase grants every new table in public to anon, authenticated and service_role. Take that
-- back and grant only what each role needs. TRUNCATE in particular is not covered by row-level
-- security, so nobody outside the database owner keeps it.
revoke all on public.members, public.briefs, public.decisions, public.files, public.checks, public.config,
  public.events, public.drafts, public.private_drafts, public.audit
  from public, anon, authenticated, service_role;

grant select on public.members, public.briefs, public.decisions, public.files, public.checks, public.config,
  public.events, public.drafts, public.audit to authenticated;
grant insert (user_id, role, display_name, active), update (role, display_name, active) on public.members to authenticated;
grant insert on public.briefs, public.decisions, public.events to authenticated;
grant insert, update on public.files, public.checks, public.config to authenticated;
grant select, insert, update on public.private_drafts to authenticated;

-- The draft-brief function: who may draft, how many drafts they asked for, the file's decisions
-- with the briefs they name (for the reviewer notes), the four-eyes setting, and each draft's
-- record. Nothing else.
grant select on public.members, public.drafts, public.decisions, public.briefs, public.config to service_role;
grant insert on public.drafts to service_role;

revoke all on all functions in schema private from public;
grant execute on function private.my_role(), private.at_least(text), private.role_rank(text) to authenticated, service_role;

alter table public.members enable row level security;
alter table public.briefs enable row level security;
alter table public.decisions enable row level security;
alter table public.files enable row level security;
alter table public.checks enable row level security;
alter table public.config enable row level security;
alter table public.events enable row level security;
alter table public.drafts enable row level security;
alter table public.private_drafts enable row level security;
alter table public.audit enable row level security;

-- Every active member reads the shared records. Someone signed in who is not a member reads nothing.
-- The helpers are wrapped in (select ...) so Postgres works them out once per query, not per row.
create policy members_read on public.members for select to authenticated using ((select private.my_role()) is not null);
create policy briefs_read on public.briefs for select to authenticated using ((select private.my_role()) is not null);
create policy decisions_read on public.decisions for select to authenticated using ((select private.my_role()) is not null);
create policy files_read on public.files for select to authenticated using ((select private.my_role()) is not null);
create policy checks_read on public.checks for select to authenticated using ((select private.my_role()) is not null);
create policy config_read on public.config for select to authenticated using ((select private.my_role()) is not null);
create policy events_read on public.events for select to authenticated using ((select private.my_role()) is not null);
create policy drafts_read on public.drafts for select to authenticated using ((select private.my_role()) is not null);
create policy audit_read on public.audit for select to authenticated using ((select private.my_role()) is not null);

create policy members_owner_insert on public.members for insert to authenticated with check ((select private.at_least('owner')));
create policy members_owner_update on public.members for update to authenticated using ((select private.at_least('owner'))) with check ((select private.at_least('owner')));
create policy briefs_insert on public.briefs for insert to authenticated with check ((select private.at_least('contributor')));
create policy decisions_insert on public.decisions for insert to authenticated with check ((select private.at_least('editor')));
create policy files_insert on public.files for insert to authenticated with check ((select private.at_least('contributor')));
create policy files_update on public.files for update to authenticated using ((select private.at_least('contributor'))) with check ((select private.at_least('contributor')));
create policy checks_insert on public.checks for insert to authenticated with check ((select private.at_least('contributor')));
create policy checks_update on public.checks for update to authenticated using ((select private.at_least('contributor'))) with check ((select private.at_least('contributor')));
create policy config_insert on public.config for insert to authenticated with check ((select private.at_least('editor')));
create policy config_update on public.config for update to authenticated using ((select private.at_least('editor'))) with check ((select private.at_least('editor')));
create policy events_insert on public.events for insert to authenticated with check ((select private.my_role()) is not null);

create policy private_drafts_own on public.private_drafts for all to authenticated
  using (user_id = (select auth.uid()) and (select private.my_role()) is not null)
  with check (user_id = (select auth.uid()) and (select private.my_role()) is not null);

-- ============================================================== seed and live updates

insert into public.config (key, four_eyes) values ('workflow', true);

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.members, public.briefs, public.decisions, public.files,
      public.checks, public.config, public.audit;
  end if;
end $$;
