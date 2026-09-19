-- =====================================================================
-- CareerPilot India — Supabase schema
-- idempotent migration 001
-- Tables, PostgREST exposure, indexes, RLS, and the user-files bucket
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Catalogs (service-role writes; public read via anon, SELECT only)
-- ---------------------------------------------------------------------

create table if not exists public.opportunity_sources (
  id          text primary key,
  provider    text not null,
  source_key  text not null,
  company     text not null default '',
  active      boolean not null default true,
  last_synced timestamptz,
  created_at  timestamptz not null default now(),
  unique (provider, source_key)
);

create table if not exists public.companies (
  id          text primary key,
  name        text not null unique,
  slug        text unique,
  location    text not null default '',
  website     text not null default '',
  created_at  timestamptz not null default now()
);

create table if not exists public.opportunities (
  id                 text primary key,
  provider           text not null,
  external_id        text not null,
  source_key         text not null,
  source_id          text references public.opportunity_sources(id),
  title              text not null,
  normalized_title   text not null,
  company_name       text not null,
  company_id         text references public.companies(id),
  location_raw       text not null default '',
  city               text,
  state              text,
  country            text,
  workplace_type     text not null default 'on_site'
    check (workplace_type in ('on_site','hybrid','remote')),
  remote_scope       text not null default 'none'
    check (remote_scope in ('none','india','worldwide','us','canada','uk','other')),
  description_html   text not null default '',
  description_text   text not null default '',
  requirements_html  text not null default '',
  skills             text[] not null default '{}',
  employment_type    text not null default 'full_time'
    check (employment_type in ('full_time','part_time','internship','contract','temporary')),
  experience_level   text
    check (experience_level is null or experience_level in ('fresher','entry','mid','senior','lead')),
  salary_min         numeric,
  salary_max         numeric,
  salary_currency    text,
  salary_text        text,
  posted_at          timestamptz,
  external_url       text not null default '',
  apply_url          text not null default '',
  apply_method       text not null default 'continue'
    check (apply_method in ('careerpilot','ats','continue')),
  india_eligible     text not null default 'ambiguous'
    check (india_eligible in ('eligible','not_eligible','ambiguous')),
  eligibility_reason text not null default '',
  is_internship      boolean not null default false,
  published          boolean not null default true,
  status             text not null default 'active'
    check (status in ('active','stale','archived')),
  dedup_fingerprint  text not null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (dedup_fingerprint)
);

create index if not exists opportunities_eligibility_published_idx
  on public.opportunities (published, india_eligible);
create index if not exists opportunities_city_idx
  on public.opportunities (city);
create index if not exists opportunities_internship_idx
  on public.opportunities (is_internship, published);
create index if not exists opportunities_posted_idx
  on public.opportunities (posted_at desc);

alter table public.opportunities enable row level security;
alter table public.companies enable row level security;
alter table public.opportunity_sources enable row level security;

-- Public can read the live catalog; only service-role writes.
create policy "opportunities_public_read"
  on public.opportunities for select to anon, authenticated
  using (published = true and status = 'active');
create policy "opportunities_service_write"
  on public.opportunities for all to service_role using (true) with check (true);

create policy "companies_public_read"
  on public.companies for select to anon, authenticated using (true);
create policy "companies_service_write"
  on public.companies for all to service_role using (true) with check (true);

create policy "sources_service_write"
  on public.opportunity_sources for all to service_role using (true) with check (true);
-- Sources expose no user data; keep them hidden from anon.

-- ---------------------------------------------------------------------
-- User-owned tables: RLS is user_id = (select auth.uid())
-- ---------------------------------------------------------------------

create table if not exists public.profiles (
  user_id            uuid primary key references auth.users(id) on delete cascade,
  full_name          text not null default '',
  headline           text not null default '',
  phone              text not null default '',
  city               text not null default '',
  state              text not null default '',
  education          jsonb not null default '[]'::jsonb,
  experience         jsonb not null default '[]'::jsonb,
  projects           jsonb not null default '[]'::jsonb,
  skills             text[] not null default '{}',
  resume_completeness int not null default 0,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create table if not exists public.job_preferences (
  user_id          uuid primary key references auth.users(id) on delete cascade,
  target_roles     text[] not null default '{}',
  preferred_cities text[] not null default '{}',
  preferred_states text[] not null default '{}',
  work_modes       text[] not null default '{}',
  experience_level text,
  employment_types text[] not null default '{}',
  salary_min       numeric,
  salary_max       numeric,
  remote_ok        boolean not null default false,
  updated_at       timestamptz not null default now()
);

create table if not exists public.application_preferences (
  user_id                       uuid primary key references auth.users(id) on delete cascade,
  default_resume_id             text,
  default_application_profile_id text,
  autofill_enabled              boolean not null default true,
  confirm_before_submit         boolean not null default true,
  updated_at                    timestamptz not null default now()
);

create table if not exists public.notification_preferences (
  user_id            uuid primary key references auth.users(id) on delete cascade,
  matching_jobs      boolean not null default true,
  internships        boolean not null default true,
  application_updates boolean not null default true,
  resume_suggestions boolean not null default true,
  updated_at         timestamptz not null default now()
);

create table if not exists public.application_answer_profiles (
  user_id          uuid primary key references auth.users(id) on delete cascade,
  name             text not null default '',
  email            text,
  phone            text not null default '',
  work_experience  jsonb not null default '[]'::jsonb,
  education        jsonb not null default '[]'::jsonb,
  skills           text[] not null default '{}',
  links            text[] not null default '{}',
  confirmed_fields text[] not null default '{}',
  updated_at       timestamptz not null default now()
);

-- Resumes live in Storage; metadata lives here (one row per upload).
create table if not exists public.resumes (
  id               text primary key,
  user_id          uuid not null references auth.users(id) on delete cascade,
  original_filename text not null,
  stored_filename  text not null,
  file_type        text not null check (file_type in ('pdf','docx')),
  file_size        integer not null default 0,
  parse_status     text not null default 'pending',
  parse_error      text,
  created_at       timestamptz not null default now()
);
create index if not exists resumes_user_idx on public.resumes (user_id, created_at desc);

create table if not exists public.resume_versions (
  id                    text primary key,
  user_id               uuid not null references auth.users(id) on delete cascade,
  parent_resume_id      text references public.resumes(id) on delete cascade,
  target_opportunity_id text,
  version_label         text not null default '',
  version_number        integer not null default 1,
  stored_filename       text not null,
  file_type             text not null default 'pdf',
  parsed_data           jsonb not null default '{}'::jsonb,
  enhancement_metadata  jsonb not null default '{}'::jsonb,
  created_at            timestamptz not null default now(),
  unique (parent_resume_id, version_number)
);

create table if not exists public.saved_opportunities (
  user_id         uuid not null references auth.users(id) on delete cascade,
  opportunity_id  text not null references public.opportunities(id) on delete cascade,
  saved_at        timestamptz not null default now(),
  primary key (user_id, opportunity_id)
);
create index if not exists saved_opportunities_user_idx
  on public.saved_opportunities (user_id, saved_at desc);

create table if not exists public.applications (
  id                 text primary key,
  user_id            uuid not null references auth.users(id) on delete cascade,
  opportunity_id     text not null references public.opportunities(id),
  company_snapshot   jsonb not null default '{}'::jsonb,
  role_snapshot      jsonb not null default '{}'::jsonb,
  status             text not null default 'saved'
    check (status in ('saved','prepared','applied','interview','rejected','offer','withdrawn')),
  applied_at         timestamptz,
  resume_version_id  text references public.resume_versions(id),
  destination        text not null default 'continue'
    check (destination in ('careerpilot','ats','continue')),
  destination_url    text not null default '',
  notes              text not null default '',
  answer_summary     jsonb not null default '{}'::jsonb,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);
create index if not exists applications_user_idx on public.applications (user_id, updated_at desc);

create table if not exists public.notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  type       text not null,
  title      text not null,
  body       text not null default '',
  read_at    timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists notifications_user_idx on public.notifications (user_id, created_at desc);

-- Row Level Security for every user-owned table
do $$
declare t text;
begin
  foreach t in array array['profiles','job_preferences','application_preferences',
                          'notification_preferences','application_answer_profiles',
                          'resumes','resume_versions','saved_opportunities','applications',
                          'notifications']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format($own$create policy "%1$s_owner" on public.%1$I for all
      to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()))$own$, t);
  end loop;
end $$;

-- ---------------------------------------------------------------------
-- Storage: private user-files bucket
-- Owner access to path <user_id>/<filename> and nothing else.
-- ---------------------------------------------------------------------

insert into storage.buckets (id, name, public)
values ('user-files', 'user-files', false)
on conflict (id) do nothing;

create policy "user_files_owner_read" on storage.objects
  for select to authenticated
  using (bucket_id = 'user-files' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "user_files_owner_insert" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'user-files' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "user_files_owner_update" on storage.objects
  for update to authenticated
  using (bucket_id = 'user-files' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "user_files_owner_delete" on storage.objects
  for delete to authenticated
  using (bucket_id = 'user-files' and (storage.foldername(name))[1] = auth.uid()::text);

-- Service role bypasses RLS automatically (bypasses_rls); no extra policy needed.

-- ---------------------------------------------------------------------
-- Keep updated_at fresh
-- ---------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at := now();
  return new;
end $$ language plpgsql;

do $$
declare t text;
begin
  foreach t in array array['profiles','job_preferences','application_preferences',
                          'notification_preferences','applications','opportunities']
  loop
    execute format('drop trigger if exists trg_%1$s_updated on public.%1$I', t);
    execute format('create trigger trg_%1$s_updated before update on public.%1$I
        for each row execute function public.set_updated_at()', t);
  end loop;
end $$;

COMMIT;