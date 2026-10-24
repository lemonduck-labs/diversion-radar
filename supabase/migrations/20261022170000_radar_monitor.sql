-- The monitor (phase 7): a person's decision on each monitoring item.
--
-- The items themselves are files built with the page (data/monitor.json, from monitor/items.jsonl,
-- each checked by fd-core's monitor module before it was filed). This table holds only what a
-- person decided: accepted with a grade on the six-by-six scale, or rejected with a reason. Any
-- Contributor decides or changes a decision; nobody deletes one. The database sets who and when,
-- and the audit log holds every change. Only accepted items appear on a file.

create table public.monitor_decisions (
  item text primary key check (item ~ '^mon-[0-9a-f]{12}$'),
  decision text not null check (decision in ('accepted', 'rejected')),
  grade text check (grade is null or grade ~ '^[A-F][1-6]$'),
  reason text check (reason is null or reason in ('not_relevant', 'duplicate', 'unreliable', 'out_of_date')),
  decided_by uuid,
  decided_at timestamptz not null default now(),
  constraint monitor_accepted_has_a_grade check (decision <> 'accepted' or (grade is not null and reason is null)),
  constraint monitor_rejected_has_a_reason check (decision <> 'rejected' or (reason is not null and grade is null))
);
comment on table public.monitor_decisions is 'A person''s decision on a monitoring item: accepted with a grade, or rejected with a reason. No deletes.';

create function private.monitor_before() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'UPDATE' and new.item <> old.item then perform private.refuse('a decision''s item cannot change'); end if;
  if tg_op = 'UPDATE' and (new.decision, new.grade, new.reason) is not distinct from (old.decision, old.grade, old.reason) then
    new.decided_by := old.decided_by; new.decided_at := old.decided_at;
  else
    new.decided_by := auth.uid(); new.decided_at := now();
  end if;
  return new;
end $$;
create trigger monitor_before before insert or update on public.monitor_decisions for each row execute function private.monitor_before();

create function private.audit_monitor() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  claims jsonb;
begin
  if tg_op = 'UPDATE' and (new.decision, new.grade, new.reason) is not distinct from (old.decision, old.grade, old.reason) then return null; end if;
  begin claims := nullif(current_setting('request.jwt.claims', true), '')::jsonb; exception when others then claims := null; end;
  insert into public.audit (at, actor, actor_role, table_name, op, row_key, lead, ref, run, action, detail, change)
  values (now(), auth.uid(), coalesce(claims ->> 'role', 'database'), 'monitor_decisions', tg_op, new.item, null, null, null,
          case when tg_op = 'UPDATE' then 'monitor_changed' when new.decision = 'accepted' then 'monitor_accepted' else 'monitor_rejected' end,
          new.item || case when tg_op = 'UPDATE' then ': ' || old.decision || ' (' || coalesce(old.grade, old.reason) || ') to ' else ' ' end
            || new.decision || ' (' || coalesce(new.grade, new.reason) || ')',
          case tg_op when 'INSERT' then jsonb_build_object('new', jsonb_build_object('decision', new.decision, 'grade', new.grade, 'reason', new.reason))
               else jsonb_build_object('old', jsonb_build_object('decision', old.decision, 'grade', old.grade, 'reason', old.reason),
                                       'new', jsonb_build_object('decision', new.decision, 'grade', new.grade, 'reason', new.reason)) end);
  return null;
end $$;
create trigger monitor_audit after insert or update on public.monitor_decisions for each row execute function private.audit_monitor();
create trigger monitor_no_truncate before truncate on public.monitor_decisions for each statement execute function private.refuse_truncate();

revoke all on function private.monitor_before(), private.audit_monitor() from public;
revoke all on public.monitor_decisions from public, anon, authenticated, service_role;
grant select on public.monitor_decisions to authenticated;
grant insert (item, decision, grade, reason), update (decision, grade, reason) on public.monitor_decisions to authenticated;
alter table public.monitor_decisions enable row level security;
create policy monitor_read on public.monitor_decisions for select to authenticated using ((select private.my_role()) is not null);
create policy monitor_insert on public.monitor_decisions for insert to authenticated with check ((select private.at_least('contributor')));
create policy monitor_update on public.monitor_decisions for update to authenticated using ((select private.at_least('contributor'))) with check ((select private.at_least('contributor')));

do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.monitor_decisions;
  end if;
end $$;
