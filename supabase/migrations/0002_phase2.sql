-- =====================================================================
-- CareerPilot India — schema 002 (phase 2: onboarding, admin, AI usage,
-- audit, analytics, resume lifecycle)
-- Additive + idempotent. Run after 0001_init.sql.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Profiles: onboarding completion flag
-- ---------------------------------------------------------------------
alter table public.profiles
  add column if not exists onboarding_completed boolean not null default false;

-- Resumes: AI-parsed structured snapshot (derived; never the original file)
alter table public.resumes
  add column if not exists parsed_data jsonb not null default '{}'::jsonb;

-- Opportunities: store the untouched provider payload (V1 `jobs.raw_payload`)
alter table public.opportunities
  add column if not exists raw_payload jsonb not null default '{}'::jsonb;

-- Resume versions: soft-delete lifecycle
alter table public.resume_versions
  add column if not exists status text not null default 'active'
    check (status in ('active','archived'));

-- Applications: allow the `archived` status the application tracker uses
do $$
begin
  if exists (
    select 1 from pg_constraint where conname = 'applications_status_check'
  ) then
    alter table public.applications drop constraint applications_status_check;
  end if;
end $$;
alter table public.applications add constraint applications_status_check
  check (status in ('saved','prepared','applied','interview','rejected','offer','withdrawn','archived'));

-- ---------------------------------------------------------------------
-- Admin role: membership table + helper (server-side authorization)
-- ---------------------------------------------------------------------
create table if not exists public.admins (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create or replace function public.is_admin()
returns boolean
language sql
stable security definer
as $$
  select exists (select 1 from public.admins where user_id = auth.uid());
$$;

alter table public.admins enable row level security;
create policy "admins_service_write" on public.admins for all to service_role using (true) with check (true);
-- Admin membership itself is only readable server-side (service_role / another admin).

-- ---------------------------------------------------------------------
-- AI usage logging
-- ---------------------------------------------------------------------
create table if not exists public.ai_usage_logs (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  feature       text not null, -- parsing | analysis | enhancement | tailoring
  model         text not null default '',
  tokens_input  integer not null default 0,
  tokens_output integer not null default 0,
  cost_usd      numeric not null default 0,
  success       boolean not null default true,
  error         text not null default '',
  created_at    timestamptz not null default now()
);
create index if not exists ai_usage_user_idx on public.ai_usage_logs (user_id, created_at desc);
create index if not exists ai_usage_feature_idx on public.ai_usage_logs (feature, created_at desc);
alter table public.ai_usage_logs enable row level security;
create policy "ai_usage_service_write" on public.ai_usage_logs for all to service_role using (true) with check (true);
create policy "ai_usage_admin_select" on public.ai_usage_logs for select to authenticated
  using (public.is_admin());

-- ---------------------------------------------------------------------
-- Product analytics (server-side written; admin readable)
-- ---------------------------------------------------------------------
create table if not exists public.analytics_events (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete set null,
  event_type  text not null,
  properties  jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists analytics_events_type_idx on public.analytics_events (event_type, created_at desc);
alter table public.analytics_events enable row level security;
create policy "analytics_service_write" on public.analytics_events for all to service_role using (true) with check (true);
create policy "analytics_admin_select" on public.analytics_events for select to authenticated
  using (public.is_admin());

-- ---------------------------------------------------------------------
-- Audit logging (server-side only; never written by clients)
-- ---------------------------------------------------------------------
create table if not exists public.audit_logs (
  id            uuid primary key default gen_random_uuid(),
  actor_user_id uuid references auth.users(id) on delete set null,
  action        text not null, -- source.create | user.role_change | job.archive | resume.support_access | ...
  resource_type text not null default '',
  resource_id   text not null default '',
  metadata      jsonb not null default '{}'::jsonb,
  ip_address    text not null default '',
  user_agent    text not null default '',
  created_at    timestamptz not null default now()
);
create index if not exists audit_logs_actor_idx on public.audit_logs (actor_user_id, created_at desc);
create index if not exists audit_logs_action_idx on public.audit_logs (action, created_at desc);
alter table public.audit_logs enable row level security;
create policy "audit_service_write" on public.audit_logs for all to service_role using (true) with check (true);
create policy "audit_admin_select" on public.audit_logs for select to authenticated
  using (public.is_admin());

-- ---------------------------------------------------------------------
-- Spec-named read views over the existing catalog tables.
-- These expose the same rows with the naming the V1 contract uses.
-- security_invoker keeps the base tables' RLS as the security boundary, so
-- each user sees exactly what the underlying row policies allow.
-- ---------------------------------------------------------------------
create or replace view public.job_sources with (security_invoker = true) as
  select id, provider as source_type, source_key as board_identifier, company as company_name,
         active as is_active, last_synced as last_synced_at, created_at
  from public.opportunity_sources;

create or replace view public.jobs with (security_invoker = true) as
  select id, provider as source, external_id as source_job_id, source_key,
         title, description_text as description, location_raw,
         city as location_city, country as location_country,
         (workplace_type = 'remote') as is_remote, workplace_type as work_mode,
         employment_type, apply_url, skills, experience_level,
         posted_at, created_at as first_seen_at, updated_at, status,
         raw_payload
  from public.opportunities;

create or replace view public.saved_jobs with (security_invoker = true) as
  select user_id, opportunity_id as job_id, saved_at
  from public.saved_opportunities;

grant select on public.job_sources, public.jobs, public.saved_jobs to authenticated;

COMMIT;