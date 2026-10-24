-- Closing the loop (phase 6.5): what happened after a lead, and the record behind a route put
-- forward for an end-use controls decision.
--
-- outcomes: the page's outcomes/<file> record (app/src/page.js, saveOutcome). One per file at a
-- run, from a fixed list, with an optional note the page screens. Any Contributor records or
-- changes it; nobody deletes one. The database sets who and when, refuses an outcome on a file
-- whose brief is not decided, and allows only "no further action" or "keep on watch" on a
-- rejected lead. The audit log holds every change.
--
-- enduse_records: the page's enduse/<file> record (saveEnduse, approveEnduse). Why the route,
-- what was checked, and the team's recommendation. Putting a route forward needs every check,
-- including information beyond the trade statistics: a lead is never the sole basis for a
-- notice. Any change to the content clears the approval; an approval needs an editor who did not
-- record it. The database sets every who and when.
--
-- A referral pack changes no table, so its export is a page event, like the evidence pack.

create table public.outcomes (
  lead text primary key check (lead ~ '^[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}$'),
  run text not null check (run ~ '^[0-9]{4}-[0-9]{2}$'),
  series text check (series is null or length(series) <= 80),
  outcome text not null check (outcome in ('no_action', 'watch', 'outreach', 'referral', 'enduse')),
  note text not null default '' check (char_length(note) <= 240),
  recorded_by uuid,
  recorded_at timestamptz not null default now()
);
comment on table public.outcomes is 'What happened after a lead, from a fixed list, once its brief is decided. A count of what the team did, never a finding. No deletes.';

create function private.decided_state(f text) returns text
language sql stable security definer set search_path = '' as $$
  -- The latest decision on the file that a page would count: approved, rejected, returned or reopened.
  select d.decision from public.decisions d where d.lead = f order by d.decided_at desc, d.id desc limit 1
$$;

create function private.outcomes_before() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  st text := private.decided_state(new.lead);
begin
  if tg_op = 'UPDATE' and (new.lead <> old.lead or new.run <> old.run) then
    perform private.refuse('an outcome''s file and run cannot change');
  end if;
  if st is null or st not in ('approved', 'rejected') then
    perform private.refuse('an outcome is recorded once the brief is approved or rejected');
  end if;
  if st = 'rejected' and new.outcome not in ('no_action', 'watch') then
    perform private.refuse('a rejected lead can only be closed or kept on watch');
  end if;
  if tg_op = 'UPDATE' and old.outcome = 'enduse' and new.outcome <> 'enduse'
     and exists (select 1 from public.enduse_records r where r.lead = new.lead and r.recommendation = 'forward') then
    perform private.refuse('a decision record puts this route forward: change the record first');
  end if;
  if tg_op = 'UPDATE' and (new.outcome, new.note) is not distinct from (old.outcome, old.note) then
    new.recorded_by := old.recorded_by; new.recorded_at := old.recorded_at;   -- nothing changed
  else
    new.recorded_by := auth.uid(); new.recorded_at := now();
  end if;
  return new;
end $$;
create trigger outcomes_before before insert or update on public.outcomes for each row execute function private.outcomes_before();

create function private.audit_outcome() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  claims jsonb;
  label text;
begin
  if tg_op = 'UPDATE' and (new.outcome, new.note) is not distinct from (old.outcome, old.note) then return null; end if;
  begin claims := nullif(current_setting('request.jwt.claims', true), '')::jsonb; exception when others then claims := null; end;
  label := case new.outcome when 'no_action' then 'No further action' when 'watch' then 'Keep on watch'
    when 'outreach' then 'Guidance or outreach to the trade' when 'referral' then 'Referred on'
    else 'Put forward for an end-use controls decision' end;
  insert into public.audit (at, actor, actor_role, table_name, op, row_key, lead, ref, run, action, detail, change)
  values (now(), auth.uid(), coalesce(claims ->> 'role', 'database'), 'outcomes', tg_op, new.lead, new.lead, private.file_ref(new.lead), new.run,
          case tg_op when 'INSERT' then 'outcome_recorded' else 'outcome_changed' end,
          left(label || case when new.note <> '' then ': ' || new.note else '' end, 200),
          case tg_op when 'INSERT' then jsonb_build_object('new', to_jsonb(new))
               else jsonb_build_object('old', jsonb_build_object('outcome', old.outcome, 'note', old.note), 'new', jsonb_build_object('outcome', new.outcome, 'note', new.note)) end);
  return null;
end $$;
create trigger outcomes_audit after insert or update on public.outcomes for each row execute function private.audit_outcome();
create trigger outcomes_no_truncate before truncate on public.outcomes for each statement execute function private.refuse_truncate();

create table public.enduse_records (
  lead text primary key check (lead ~ '^[0-9]{4}-[0-9]{2}_[A-Z]{2}-[0-9]{4,8}$'),
  run text not null check (run ~ '^[0-9]{4}-[0-9]{2}$'),
  series text check (series is null or length(series) <= 80),
  reasons text not null check (length(btrim(reasons)) between 1 and 600),
  checks text[] not null default '{}' check (checks <@ array['onward', 'chpl', 'display', 'cases', 'partners', 'beyond']),
  recommendation text not null check (recommendation in ('forward', 'not_now')),
  approved boolean not null default false,
  recorded_by uuid,
  recorded_at timestamptz not null default now(),
  -- Everyone who wrote the content since the last approval: none of them may approve it.
  recorders uuid[] not null default '{}',
  approved_by uuid,
  approved_at timestamptz,
  -- Putting a route forward needs every check: a lead is never the sole basis for a notice.
  constraint enduse_forward_needs_every_check check (recommendation <> 'forward' or checks @> array['onward', 'chpl', 'display', 'cases', 'partners', 'beyond'])
);
comment on table public.enduse_records is 'Why a route was put to the people who decide whether exporters are informed, what was checked and the team''s recommendation, approved by a second editor. No deletes.';

create function private.enduse_before() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' and (new.lead <> old.lead or new.run <> old.run) then
    perform private.refuse('a decision record''s file and run cannot change');
  end if;
  if not exists (select 1 from public.outcomes o where o.lead = new.lead and o.outcome = 'enduse') then
    perform private.refuse('a decision record needs the outcome "put forward for an end-use controls decision"');
  end if;
  if tg_op = 'INSERT' or (new.reasons, new.checks, new.recommendation) is distinct from (old.reasons, old.checks, old.recommendation) then
    -- New content is a new record: whoever wrote it recorded it, and it needs a fresh approval.
    new.recorded_by := auth.uid(); new.recorded_at := now();
    new.recorders := case when tg_op = 'UPDATE' and not old.approved then array(select distinct x from unnest(old.recorders || auth.uid()) x) else array[auth.uid()] end;
    new.approved := false; new.approved_by := null; new.approved_at := null;
    return new;
  end if;
  new.recorded_by := old.recorded_by; new.recorded_at := old.recorded_at; new.recorders := old.recorders;
  if new.approved and not old.approved then
    if not (select private.at_least('editor')) then perform private.refuse('only an editor approves a decision record'); end if;
    if auth.uid() = any(old.recorders) then perform private.refuse('a person who wrote this record cannot approve it'); end if;
    new.approved_by := auth.uid(); new.approved_at := now();
  elsif not new.approved and old.approved then
    perform private.refuse('an approval is cleared only by changing the record');
  else
    new.approved_by := old.approved_by; new.approved_at := old.approved_at;
  end if;
  return new;
end $$;
create trigger enduse_before before insert or update on public.enduse_records for each row execute function private.enduse_before();

create function private.audit_enduse() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  claims jsonb;
  act text;
begin
  if tg_op = 'UPDATE' and (new.reasons, new.checks, new.recommendation, new.approved) is not distinct from (old.reasons, old.checks, old.recommendation, old.approved) then return null; end if;
  begin claims := nullif(current_setting('request.jwt.claims', true), '')::jsonb; exception when others then claims := null; end;
  act := case when tg_op = 'UPDATE' and new.approved and not old.approved then 'enduse_approved' else 'enduse_recorded' end;
  insert into public.audit (at, actor, actor_role, table_name, op, row_key, lead, ref, run, action, detail, change)
  values (now(), auth.uid(), coalesce(claims ->> 'role', 'database'), 'enduse_records', tg_op, new.lead, new.lead, private.file_ref(new.lead), new.run, act,
          case new.recommendation when 'forward' then 'Put forward for a decision on informing exporters of these goods to this destination' else 'Not put forward now' end,
          jsonb_build_object('new', jsonb_build_object('reasons', new.reasons, 'checks', new.checks, 'recommendation', new.recommendation, 'approved', new.approved)));
  return null;
end $$;
create trigger enduse_audit after insert or update on public.enduse_records for each row execute function private.audit_enduse();
create trigger enduse_no_truncate before truncate on public.enduse_records for each statement execute function private.refuse_truncate();

revoke all on function private.decided_state(text), private.outcomes_before(), private.audit_outcome(), private.enduse_before(), private.audit_enduse() from public;
revoke all on public.outcomes, public.enduse_records from public, anon, authenticated, service_role;
grant select on public.outcomes, public.enduse_records to authenticated;
grant insert (lead, run, series, outcome, note), update (outcome, note) on public.outcomes to authenticated;
grant insert (lead, run, series, reasons, checks, recommendation), update (reasons, checks, recommendation, approved) on public.enduse_records to authenticated;
alter table public.outcomes enable row level security;
alter table public.enduse_records enable row level security;
create policy outcomes_read on public.outcomes for select to authenticated using ((select private.my_role()) is not null);
create policy outcomes_insert on public.outcomes for insert to authenticated with check ((select private.at_least('contributor')));
create policy outcomes_update on public.outcomes for update to authenticated using ((select private.at_least('contributor'))) with check ((select private.at_least('contributor')));
create policy enduse_read on public.enduse_records for select to authenticated using ((select private.my_role()) is not null);
create policy enduse_insert on public.enduse_records for insert to authenticated with check ((select private.at_least('contributor')));
create policy enduse_update on public.enduse_records for update to authenticated using ((select private.at_least('contributor'))) with check ((select private.at_least('contributor')));

-- The referral pack's export is a page event.
alter table public.events drop constraint events_action_check;
alter table public.events add constraint events_action_check check (action in ('pack_exported', 'audit_exported', 'exporter_screened', 'exporter_exported', 'referral_exported'));

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.outcomes, public.enduse_records;
  end if;
end $$;
