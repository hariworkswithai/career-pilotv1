-- =====================================================================
-- CareerPilot India — Supabase schema migration 003
-- Phase 2 search platform: trigram + full-text search, source sync health
-- Idempotent. Run after 0002_phase2.sql.
-- =====================================================================

BEGIN;

-- Trigram support for fuzzy city/title matching (autocomplete, search).
create extension if not exists pg_trgm;

-- Full-text search vector over title + company + description + skills,
-- maintained by trigger so application code never computes it by hand.
alter table public.opportunities
  add column if not exists search_vector tsvector;

create or replace function public.opportunities_search_trigger()
returns trigger
language plpgsql
as $$
begin
  new.search_vector :=
    setweight(to_tsvector('english', coalesce(new.title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(new.company_name, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(new.description_text, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(array_to_string(new.skills, ' '), '')), 'B');
  return new;
end;
$$;

drop trigger if exists opportunities_search_vector_trigger on public.opportunities;
create trigger opportunities_search_vector_trigger
  before insert or update
  on public.opportunities
  for each row execute function public.opportunities_search_trigger();

-- Backfill rows ingested before this migration.
-- Computed inline (not via a dummy self-assignment) so the backfill depends
-- only on columns guaranteed by 0001 (title, company_name, description_text,
-- skills) and on no trigger firing. Same expression as the trigger function.
update public.opportunities
set search_vector =
  setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
  setweight(to_tsvector('english', coalesce(company_name, '')), 'B') ||
  setweight(to_tsvector('english', coalesce(description_text, '')), 'C') ||
  setweight(to_tsvector('english', coalesce(array_to_string(skills, ' '), '')), 'B')
where search_vector is null;

create index if not exists opportunities_search_vector_idx
  on public.opportunities using gin (search_vector);

-- Trigram indexes for fuzzy matching (city autocomplete, title search).
create index if not exists opportunities_city_trgm_idx
  on public.opportunities using gin (city gin_trgm_ops);

create index if not exists opportunities_title_trgm_idx
  on public.opportunities using gin (title gin_trgm_ops);

-- Freshness lifecycle needs the `expired` status (was active/stale/archived).
do $$
begin
  if exists (
    select 1 from pg_constraint where conname = 'opportunities_status_check'
  ) then
    alter table public.opportunities drop constraint opportunities_status_check;
  end if;
end $$;
alter table public.opportunities add constraint opportunities_status_check
  check (status in ('active','stale','expired','archived'));

-- Source sync health tracked by the ingestion pipeline / admin API.
alter table public.opportunity_sources
  add column if not exists last_sync_status text not null default 'never';

alter table public.opportunity_sources
  add column if not exists last_error text not null default '';

-- Audit log retention queries (admin UI pages newest-first).
create index if not exists audit_logs_created_idx
  on public.audit_logs (created_at desc);

COMMIT;
