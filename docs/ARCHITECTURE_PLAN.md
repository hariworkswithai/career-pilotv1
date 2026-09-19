# CareerPilot India — Phase 0 Architecture & Implementation Plan

> **Update:** See `TECH_STACK_AND_SETUP.md` for the finalized stack, external-service
> cards (verified against current official docs), endpoint/credential/env-var lists,
> and the finalized repo layout (which supersedes the `apps/web`+`apps/api` naming here).

Status: DRAFT (awaiting approval — Phase 1 starts only after this is approved)
Product: CareerPilot India — AI-powered, India-first career platform
Scope: India jobs + internships, matching, resume analysis/enhancement/tailoring, application preparation, tracking.

---

## 0. Environment Inspection Findings

**Location:** `C:\Users\HP\OneDrive\Documents\Default Project` (not a git repo at root).

Existing projects found (per instructions: do **not** delete or modify before/without approval):

| Folder | What it is | Relevance to new build |
|---|---|---|
| `careerpilot/` | Next.js 16.3.4 app (v1) | Large surface area; includes certifications, skill-growth, career-roadmap, learning, advisor features — much of it out of scope for the new product. Not trusted. |
| `careerpilot-v2/` | Next.js 16.3.5 app (v2) | Matching engine, Greenhouse/Lever/Ashby providers, cross-provider dedup, resume parsing (mammoth/pdf-parse), application tracker, grounded answer drafting, certifications module. Fully Next-only (no separate backend; ingestion is a request-triggered job). Not trusted wholesale. |
| `careerpilot-extension/` | Chrome MV3 autofill extension (ATS: Greenhouse, Lever, Ashby, Workday, SmartRecruiters) | Conceptually relevant to "Apply with CareerPilot"; build is an extension, separate lifecycle. |
| `node_modules/`, `.pytest_cache/` | Loose artifacts at root | Ignore. |

**Decisions already confirmed with the stakeholder:**
1. New codebase lives in a fresh top-level directory: `Default Project\careerpilot-v3\`.
2. Single monorepo, two apps: `apps/web` (Next.js) + `apps/api` (FastAPI), plus a generated shared API client package.

**Why build from scratch and not fork v2:** v2 mixes ingestion, matching, and AI orchestration into Next.js server code with certification features and application flows that do not match the new specification (no certifications; India-only eligibility is a backend concern; a real ingestion pipeline and AI provider abstraction are required). A clean, separately-serviced architecture is cheaper to secure, test, and evolve than refactoring v2 in place. Existing projects remain untouched and can be referenced for ideas, but are not source-of-truth.

---

## 1. Technology Stack

| Layer | Choice | Version basis |
|---|---|---|
| Monorepo tooling | npm workspaces (single `package.json` at root) + Python managed per-app | Keep tooling minimal |
| Frontend | Next.js (App Router) + React 19 + TypeScript 5 | Pin the current stable line already proven in this environment: Next 16.x, React 19.x |
| Styling | Tailwind CSS v4 (+ `tailwindcss/postcss`) | Proven in environment |
| Data fetching/auth client | `@supabase/ssr` + `@supabase/supabase-js` (browser-side auth/session only) | |
| Backend | Python 3.12+, FastAPI, Pydantic v2, uvicorn, httpx | Async, schema-driven, typed |
| Database/Storage/Auth | Supabase (Postgres + Auth + Storage) | Managed, RLS-native |
| Job providers | httpx-based clients over Greenhouse & Ashby public board APIs | Provider abstraction (Protocol) |
| PDF text extraction | `pypdf` + `pdfplumber` (MIT) | Untrusted-file safe(ish); no AGPL (avoids PyMuPDF licensing friction) |
| DOCX extraction | `python-docx` (MIT) | |
| AI | Provider abstraction; initial implementation `OpenRouterProvider` (OpenAI-compatible chat-completions + JSON mode) + `MockProvider` (tests/fallback) | No lock-in to one vendor |
| Testing | `pytest` + `httpx`/`TestClient` (backend), Vitest (frontend), Playwright (E2E) | |
| Python env | `uv` or `pip` + `pyproject.toml` (single backend dependency manifest) | TBD at Phase 1 |
| Local Supabase | Supabase CLI (`supabase start` / `db reset`) | Migrations from the start |

**Why:** matches the spec's "Recommended: Next.js" and "Recommended: FastAPI Python". A separate Python backend gives a safe home for ingestion, matching, resume processing, and AI orchestration (heavy/CPU/LLM work) and keeps secrets server-side. Alternative considered: keep everything in Next.js API routes (v2's approach) — simpler initially, but couples ingestion/matching/AI to the web server, complicates scheduled sync, and makes security isolation weaker. The two-app split is chosen.

**Anti-over-engineering rules:** no Redis, no Celery, no message queue, no separate DB server, no Kubernetes at this stage. A single FastAPI process with an internal scheduled job and per-process rate limiter is enough for launch.

---

## 2. Repository Structure

```
Default Project\careerpilot-v3\
  .env.example                     # all variable names, no values
  .gitignore                       # .env, .env.local, node_modules, .next, __pycache__, etc.
  package.json                     # npm workspaces root (web + shared client)
  README.md
  docs\
    ARCHITECTURE_PLAN.md           # this document
    DATABASE.md                    # full schema + migrations catalog + RLS policies
    API.md                         # OpenAPI contract notes + endpoint map
    DECISIONS.md                   # ADR log (each major decision + rationale)
    TESTING.md
    ENV.md                         # generated variable reference
  apps\
    web\                           # Next.js App Router
      src\
        app\                       # (auth), (app) route groups, API-free pages
        components\ui\             # button, input, card, dialog, select, badge, chips, autocomplete
        components\domain\         # job-card, match-explanation, resume-wizard, application-tracker...
        lib\                       # generated api client, supabase client, auth guards
        middleware.ts              # session refresh + route protection
        types\
      package.json
      next.config.ts
      tsconfig.json
      vitest.config.ts
      eslint.config.mjs
    api\                           # FastAPI
      app\
        main.py                    # app factory, middleware, routers mount
        core\                      # config (env), security (jwt verify, rate limit, sanitize)
        db\                        # supabase/PostgREST client + sql queries (or SQLAlchemy sync driver)
        schemas\                   # Pydantic request/response models
        routers\
          auth.py, profile.py, preferences.py, opportunities.py,
          resumes.py, analysis.py, enhancement.py, applications.py,
          saved.py, notifications.py, settings.py, internal\sync.py
        services\
          ingestion\               # provider abstraction + pipeline
          matching\                # deterministic matcher
          locations\               # India location normalization + eligibility
          resumes\                 # upload/validate/extract/parse
          ai\                      # provider abstraction + prompts + guardrails
          applications\            # statuses, drafting, sensitive-question policy
        tests\
          unit\, integration\, api\, security\
      pyproject.toml
      .env.example                 # (or use root)
      Dockerfile                   # Phase 23
  packages\
    api-client\                    # TS client generated from FastAPI OpenAPI (openapi-typescript)
      src\generated\
      package.json
  scripts\
    dev.ps1 / dev.sh               # start supabase + api + web together
    gen-client.<sh/ps1>
  infrastructure\
    supabase\                      # supabase CLI config: config.toml, migrations\
      0001_init.sql ...            # forward-only migrations
```

**Why:** npm workspaces keep the web + generated client in one toolchain; Python has its own isolated dependency tree; a single `infrastructure/supabase/migrations` folder is authoritative for DB (never hand-edited in production). Alternative considered: monorepo-wide Python+Node tool (Turborepo/Nx) — rejected as over-engineering.

---

## 3. Database Schema (Design)

All tables in Postgres via Supabase. UUID primary keys. Every user-owned table has `user_id` (FK → `auth.users.id`). Timestamps `created_at`/`updated_at`.

**Entities:**

1. **profiles** — identity + career facts (user-curated canonical store)
   - `user_id` PK, full_name, headline, phone, location_city/state, bio/objective
   - `education jsonb` (degree, institution, year…), `experience jsonb` (role, company, duration, bullets), `projects jsonb`, `skills text[]`
   - `resume_completeness` (computed, cached), timestamps
2. **job_preferences** — 1:1 with user
   - target_roles text[], preferred_cities text[] (normalized city ids), work_modes text[], experience_level, employment_types text[], salary_min/max, remote_ok bool
3. **application_preferences**
   - default_resume_id (FK resumes), default_application_profile_id, autofill_enabled bool, confirm_before_submit bool
4. **notification_preferences**
   - matching_jobs, internships, application_updates, resume_suggestions (bools); email_toggle placeholder
5. **opportunity_sources** (service-role only; RLS enabled with no policies)
   - provider, board_name/company_slug, base_url, active, last_sync_at, last_sync_status, last_error, row_count
6. **companies**
   - name, normalized_name, website, logo_url; dedup by normalized_name
7. **opportunities** — the normalized/public job+internship catalog
   - external_id (provider-scoped), source_id (FK opportunity_sources), company_id, title, normalized_title
   - description_html **sanitized**, responsibilities_html, requirements_html, skills text[]
   - city, state, country (normalized), workplace_type (onsite/hybrid/remote), remote_scope (india/worldwide/us_only/other)
   - employment_type (full_time/part_time/internship/contract), experience_level, salary_min/max/currency
   - posted_at, external_url, apply_method (careerpilot/ats/continue)
   - **india_eligible bool** + eligibility_reason (computed at ingestion, enforced in queries)
   - dedup_fingerprint (unique), status (active/stale/removed)
8. **resumes** — original uploads (immutable)
   - user_id, original_filename, stored_filename, file_type, file_size, storage_path
   - parse_status (pending/parsed/failed), parsed_text (extracted, RLS-protected), parsed_data jsonb, parse_error
9. **resume_versions** — enhanced/tailored versions
   - user_id, parent_resume_id (origin), target_opportunity_id (nullable), version_label, version_number
   - storage_path, file_type, parsed_data jsonb, enhancement_metadata jsonb (per-section change summary, model, prompt version), status, timestamps
10. **applications**
    - user_id, opportunity_id, saved_opportunity_id (nullable), company_snapshot jsonb, role_snapshot jsonb
    - status (saved/prepared/applied/interview/rejected/offer/withdrawn), applied_at, resume_version_id, application_destination, destination_url
    - answers_snapshot jsonb (only non-sensitive user-confirmed answers; sensitive legal/demographic Q&As are never stored by default), notes, timestamps
11. **saved_opportunities**
    - user_id, opportunity_id, status (active/archived), saved_at
12. **application_profiles** — grounded answer sources
    - user_id, name, email, phone, work_experience jsonb, education jsonb, skills text[], links jsonb, confirmed_fields text[]
13. **notifications**
    - user_id, type, title, body, read_at, created_at

**Why these and not more:** a schema that maps 1:1 to the product loop (profile → resume → discovery → match → enhancement → application → tracking). No tables for things the product does not do (certifications, payments, social, recruiter marketplace).

**Certifications:** fully excluded. No tables, no columns, no catalog, no features.

---

## 4. RLS Strategy

- **User-owned tables** (`profiles`, `job_preferences`, `application_preferences`, `notification_preferences`, `resumes`, `resume_versions`, `applications`, `saved_opportunities`, `application_profiles`, `notifications`):
  - `using (user_id = auth.uid())` for SELECT/UPDATE/DELETE; `with check (user_id = auth.uid())` for INSERT. No roles other than `authenticated` and `service_role`.
- **Public catalog** (`opportunities`, `companies`): SELECT open to `anon`+`authenticated`; INSERT/UPDATE/DELETE only via `service_role` (bypasses RLS) — never from the client.
- **`opportunity_sources`**: RLS enabled, **no policies** → service-role only.
- **Storage**: private bucket `user-files`, path convention `{user_id}/{category}/{file}`, policies matching `storage.foldername(name)[1] = auth.uid()::text`. Users can only reach their own prefix.
- **Defense in depth**: backend verifies ownership in application code too (never trusts RLS alone for authorization decisions that gate AI/expensive operations).

**Why:** RLS is the non-negotiable data boundary for user-owned data. Anon-readable catalog keeps signed-out browsing cheap without exposing user data. Service-role credentials live only in the FastAPI backend env.

---

## 5. API Architecture

- FastAPI serves `/api/v1/*`. Next.js is the primary consumer via a **generated typed client** (from FastAPI's OpenAPI schema) — single source of truth for contracts, no hand-maintained client.
- **Authentication:** Next.js handles login/session with Supabase Auth (browser + SSR middleware). API requests carry `Authorization: Bearer <access_token>`. FastAPI verifies the token locally with PyJWT against Supabase JWKS (cached), with `GET /auth/v1/user` fallback. This avoids a DB round-trip per request and keeps verification server-side.
- **Internal endpoints** (`/api/v1/internal/*`): guarded by a signed internal token (env), not user tokens.
- **Endpoints:**

| Area | Endpoints |
|---|---|
| Auth | `GET /me`, `PUT /profile` (Supabase handles signup/login/reset) |
| Preferences | `GET/PUT /job-preferences`, `/application-preferences`, `/notification-preferences` |
| Opportunities (public) | `GET /opportunities` (search/filter/sort/pagination), `GET /opportunities/{id}`, `GET /opportunities/{id}/match` (authed) |
| Saved | `POST/DELETE /saved`, `GET /saved` |
| Resumes | `POST /resumes` (multipart upload), `GET /resumes`, `GET /resumes/{id}`, `POST /resumes/{id}/parse`, `POST /resumes/{id}/analyze`, `POST /resumes/{id}/enhance`, `POST /resumes/{id}/tailor` (with opportunity), `POST /resumes/{id}/versions`, `GET /resumes/{id}/versions`, `GET /resumes/{id}/versions/{vid}` |
| Downloads | `GET /files/resumes/{id}` (signed, owner-only), same for versions |
| Applications | `GET/POST /applications`, `PATCH /applications/{id}` (status transition validation), `GET /applications/{id}` |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read` |
| Settings | `GET/PUT /profile`, preference endpoints above, `DELETE /account` |
| Internal | `POST /internal/sync` (ingest), `GET /internal/health` |

- **Job HTML sanitization** happens server-side on ingestion (allowlist: p, strong, em, ul, ol, li, h2, h3, a, br; strip script/iframe/object/embed/handlers/javascript: URLs/unsafe styles). Frontend additionally renders with escaping.
- **Pagination/infinite scroll:** cursor or page+size, capped page sizes; match score computed in queries/on demand (no full-dataset transfer).

**Why:** a backend-owned API keeps authorization, ingestion, AI costs, and secrets server-side; OpenAPI generation removes contract drift. Alternative considered: Next.js server actions doing everything — rejected for the reasons in §1.

---

## 6. Frontend Architecture

- **App Router structure:** route groups `(auth)` (`/login`, `/signup`) and `(app)` (all authenticated pages). Middleware refreshes sessions and redirects unauthenticated users.
- **Pages:** `/` (landing/redirect), `/dashboard`, `/jobs`, `/internships`, `/opportunities/[id]` (shared detail), `/resume` (upload + list + analysis), `/resume/versions/[id]` (enhanced view + download + change review), `/applications`, `/profile`, `/settings`.
- **Data fetching:** server components use the typed client (server-side) with access token from session; client components for interactive surfaces (filters, autocomplete, dialogs, application wizard).
- **UI:** shared `components/ui` primitives (no giant monolithic components): Button, Input, Textarea, Card, Dialog, Select, Badge, FilterChip, Autocomplete (with keyboard nav, mouse, mobile, empty/loading states, debounce), EmptyState, Skeleton, Toast.
- **Design system:** light, professional, modern; not the old dark-blue-heavy look. Information hierarchy inspired by modern job-discovery products (Jobright) in *concept only* — no copied branding/layout/text/assets. Responsive at desktop/tablet/mobile.
- **Bundle discipline:** route-level code splitting, no heavy client libs; PDF preview/download via backend-signed URL (not client PDF generation).

**Why:** server-first rendering keeps API/DB usage efficient and avoids exposing tokens widely; isolated primitives keep components testable and small.

---

## 7. Job Provider Abstraction

Python `Protocol` (typed contract), registry + factory:

```
JobProvider (Protocol)
 ├── list_sources() -> list[BoardSource]
 ├── fetch_jobs(source) -> AsyncIterator[RawJob]
 └── (impl) GreenhouseProvider
 └── (impl) AshbyProvider
```

- Each provider maps board responses → canonical `RawJob` (typed dict), provider-specific errors propagated as typed exceptions.
- **Ingestion pipeline:** fetch → validate → normalize → India-eligibility classify → dedupe → store → mark stale. Provider failures are isolated (try/except per source; one broken provider never fails the run).
- Retries/timeouts via httpx; per-source concurrency caps; row-level dedup via external ID and cross-provider dedup via `dedup_fingerprint` (normalized title + company + location bucket).
- Future providers are added as new Protocol implementations, no core changes.

**Why:** spec requires a clean abstraction; isolates provider quirks and enables adding sources later (LinkedIn/Naukri are out of scope now).

---

## 8. India Location System

- **Data module** (`service/locations`): seed list of Indian cities with (canonical name, aliases, state). Extensible — new cities are data, not code changes. Include the majors (Mumbai, Pune, Bengaluru, Hyderabad, Chennai, Delhi, Gurugram, Noida, Ahmedabad, Kolkata, …) plus a larger seed set at Phase 7.
- **Normalization pipeline** for raw location strings:
  1. Split/clean tokens; strip noise.
  2. Alias mapping (`Bangalore→Bengaluru`, `Bombay→Mumbai`, `New Delhi/Metro→Delhi`, `NCR`→ expand Gurugram/Noida/Faridabad/Ghaziabad).
  3. Country detection (India vs World/Global vs US/CA/UK/other).
  4. Workplace type (onsite/hybrid/remote).
  5. **Remote scope**: `india_remote`, `worldwide_remote`, `us_remote`, `ca_remote`, `uk_remote`, `other_remote`.
- **Eligibility classifier** (deterministic, unit-tested):
  - India city/state/`India`/`India remote` → eligible
  - `worldwide remote` → eligible (documented policy)
  - `US-only/Canada/UK/other` remote or foreign city → not eligible
  - ambiguous → **conservatively not eligible** (never accidentally shows foreign jobs)
- Eligibility is computed at **ingestion time** and stored (`india_eligible`, `eligibility_reason`); all public queries filter on the stored column — filtering is backend-enforced, not a frontend veneer.

**Why:** a data-driven location system scales to many Indian cities without code churn and gives deterministic, testable eligibility. Examples from spec verified against the classifier in tests (Bengaluru→eligible, Toronto→rejected, US-only remote→rejected).

---

## 9. Matching Architecture

Deterministic matcher first; LLM only for optional natural-language "why you match" phrasing.

- **Weights (documented product-relevance weights, config-defined, transparent, not "scientific"):**
  - Skills 40% · Experience 20% · Role relevance 20% · Location 10% · Other (work mode/employment type) 10%
- **Pipeline:** tokenize/normalize skill names (alias map + stoplist) → intersect user skills (profile + selected resume parsed data) with job skills → score overlap (weighted by skill specificity) → experience-level fit (job min vs user years) → role relevance (title keyword similarity) → location/work-mode/employment fit vs user preferences.
- **Output:** `MatchResult { score, matched_skills[], gap_skills[], breakdown{skill,experience,role,location,other}, explanation_components[] }`.
- Computed on demand for single job; batched/ordered for lists (server-side). Deterministic → unit-testable (pure functions, no I/O).
- **No fabricated scores:** score is a product relevance score derived only from real inputs.

**Why:** deterministic first per spec ("Do NOT make the entire matching system dependent on an LLM"); testable, cheap, and honest. LLM explanation layer is additive and validates against the deterministic facts.

---

## 10. Resume Architecture

- **Upload:** validate extension + **magic bytes** (not MIME alone), size cap, filename sanitization → store original bytes to private Storage (immutable original), record metadata row in `resumes`.
- **Extraction:** PDF via `pypdf` (+ `pdfplumber` refinement), DOCX via `python-docx`; reject encrypted/password-protected files; size/timeout-guarded; never trust client-supplied text.
- **Parsing:** heuristic structural parser first (sections, contact info, skills, education, experience, projects) → optional LLM structured pass (schema-validated, Pydantic) → stores `parsed_text` + `parsed_data`. Parsing never invents content.
- **Original immutability:** original file and its `resumes` row are never modified by AI features. AI always produces `resume_versions`.

**Why:** preserves the user's source of truth and makes every AI output a reviewable derivative.

---

## 11. AI Architecture

```
AIProvider (Protocol)
 ├── complete_json(system, user, output_schema) -> validated JSON
 ├── complete_text(...)
 ├── OpenRouterProvider          # production dev path (OpenAI-compatible, JSON mode)
 └── MockProvider                # tests + graceful fallback
```

- Backend-only; keys in env; never in the frontend.
- **Structured output:** every AI call returns schema-validated JSON (Pydantic); retries on malformed output; bounded output; deterministic timeouts; per-operation cost guardrails.
- **Prompt-injection hardening:** untrusted content (resume text, job descriptions) is delimited as data, system prompt prohibits following instructions found in data, output is schema-validated, and **fabrication policy** is enforced in prompts + validated by output checks (numbers/metrics must be traceable to input; extraction only). Never blindly trusted.
- **Use is deliberate:** AI used for resume wording, analysis, tailoring, and natural-language explanations only. Deterministic code owns auth/authz/eligibility/validation/DB/state/security.

**Why:** spec requires provider abstraction and controlled AI; isolation means adding/replacing providers and enforcing the no-fabrication rule are localized concerns.

---

## 12. Resume Versioning

- Oldest-to-newest: `resumes` (original) → `resume_versions` (enhanced/tailored) with `parent_resume_id`, `target_opportunity_id`, `version_label`, `version_number` (per original).
- **Change review:** enhancement returns structured per-section old/new + reason; UI shows original vs enhanced with Accept/Reject per section; accepted combination is stored as the new version snapshot (`parsed_data` + doc). Rejected edits are dropped. No silent replacement of the original.
- **Downloads:** backend issues signed, owner-scoped URLs with sensible filenames (`Hari_AI_Engineer_Resume.pdf`).
- Lineage is retained for audit + re-use across jobs.

**Why:** the product loop depends on versioned, job-specific resumes with user control; a single table with lineage is sufficient (no over-engineering).

---

## 13. Application Architecture

- **Statuses:** `saved → prepared → applied → interview → (rejected | offer)` plus `withdrawn`. Transitions validated server-side (managed state machine).
- **Application destination states:**
  1. `careerpilot` — "Apply on CareerPilot": only when an in-house supported flow exists (initial: none until we build or integrate a legit flow).
  2. `ats` — "Apply with CareerPilot": grounded drafting + review, then handoff to the ATS browser-extension (supports: Greenhouse, Lever, Ashby, Workday, SmartRecruiters as in v2's extension — re-validated in Phase 18). Extension never auto-submits.
  3. `continue` — "Continue Application": external link, tracked as prepared/applied manually.
- **Grounded drafting** from `application_profiles` + selected resume; **sensitive questions** (work auth, visa, legal declarations, demographics, criminal history) are never auto-answered — surfaced for explicit user review.
- **No unauthorized scraping** or arbitrary automated form submission.

**Why:** honest about what we can submit, keeps the user in control of consequential actions, and reuses legitimate ATS flows.

---

## 14. Settings Architecture

One Settings page backed by existing preference tables (no duplicate storage):
- Account (name/email/password via Supabase Auth), Job preferences (`job_preferences`), Application preferences (`application_preferences`), Notifications (`notification_preferences`), Privacy/Security (data controls, resume deletion, account deletion — backend endpoint `DELETE /account` removing owned rows + storage files + auth user via service role).

**Why:** settings is a UI over the same preference schema, avoiding parallel storage.

---

## 15. Security Architecture

Threat → control matrix (implemented from Phase 1, tested continuously):

- **SQL injection** → Parametrized queries/ORMs only; no string-built SQL from user input.
- **XSS** → server-side HTML sanitization on ingestion (allowlist) + escaped rendering; sanitized at write, not only at render.
- **CSRF** → SameSite cookies + bearer-token API model; state-changing admin/internal endpoints require the internal token.
- **IDOR** → ownership enforced by RLS + backend re-check on every owner-scoped operation and signed-URL issuance.
- **Path traversal** → server-generated storage keys; client filenames never used in paths.
- **Uploads** → magic-byte + extension + size + content validation; encrypted/zip-bomb handling documented (archives unsupported initially).
- **Prompt injection / data leakage** → data/content isolation in prompts, schema-validated output, no full sensitive data sent to providers, redaction of application draft answers.
- **Credential exposure** → secrets backend-only; `.env.*` gitignored; `.env.example` committed (names only); no logging of keys/passwords/full resumes.
- **Rate abuse** → per-process fixed-window limiter on auth-adjacent and expensive/AI routes (documented upgrade path to shared store pre-scale).
- **Malformed AI output / fabrication** → schema validation + fabrication checks (§11).
- **Headers** → CSP, HSTS, X-Frame-Options DENY, nosniff, strict Referrer-Policy, Permissions-Policy.

**Why:** security is designed in (authz at every boundary, untrusted-input discipline), not bolted on in Phase 23.

---

## 16. Testing Architecture

| Layer | Tool | Coverage |
|---|---|---|
| Backend unit | pytest | matching, location/eligibility, normalization, dedup, sanitization, state machine, drafting policy, security helpers |
| Backend API/integration | pytest + TestClient + Supabase local | every endpoint; auth failures; RLS enforcement via service/client duality |
| RLS/DB | SQL policy tests (run policies against Supabase local with authed client asserting cross-user isolation) | IDOR matrix: user A cannot read/write user B's resumes/applications/etc. |
| Security | pytest + targeted suites | XSS sanitizer, upload validation, prompt-injection guardrails, malformed AI output, token verification |
| Frontend unit | Vitest + Testing Library | primitives, autocomplete, filters, change-review, state reducers |
| Frontend E2E | Playwright | signup→profile→resume upload→search→match→tailor→manual apply→track (happy path + auth guard) |

**Why:** the risk concentrates in deterministic logic (eligibility, matching, dedup) and ownership boundaries, so those get the most automated coverage; E2E proves the product loop end-to-end before launch.

---

## 17. Deployment Architecture

- **Supabase:** managed (Postgres + Auth + Storage + RLS). Migrations via Supabase CLI; never hand-mutate production.
- **Backend (FastAPI):** single containerized web service on a Node-independent host — Render or Railway (uvicorn, `N` workers; graceful shutdown). Scheduled ingestion via the host's cron hitting `/internal/sync` (or Supabase pg_cron trigger → internal endpoint). No queue infra initially.
- **Frontend (Next.js):** static/server SSR on Vercel (or same host if unified later); env split for public vs server-only.
- **Env/secrets:** per-service environment config; never in repo.
- **Observability:** structured JSON logs (no secrets/resumes), error tracking (e.g., Sentry) wired to backend routes, simple provider-sync + AI-failure metrics, health endpoint `/internal/health`.

**Why:** cheapest production path that meets the spec's constraints (managed DB, no Redis/queue); host choice is swappable without architecture change.

---

## 18. Environment Variables

`.env.example` (names only; grouped). Full reference in `docs/ENV.md`:

| Group | Variables |
|---|---|
| Supabase public | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_APP_URL` |
| Supabase server | `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` (for local token verify) |
| AI | `OPENROUTER_API_KEY`, `AI_MODEL`, `AI_JSON_MODEL`, `AI_MAX_TOKENS`, `AI_TIMEOUT_MS` |
| Providers | `GREENHOUSE_SOURCES` (board slugs), `ASHBY_SOURCES`, sync-related |
| Internal | `INTERNAL_SYNC_TOKEN`, rate-limit settings |
| Storage | bucket names, signed-URL TTL |
| App | `ENVIRONMENT`, `LOG_LEVEL`, `API_CORS_ORIGINS` |

Never commit real values. **Never expose** `SUPABASE_SERVICE_ROLE_KEY`, AI keys, internal token to the frontend.

---

## 19. Development Workflow

- **Git:** init repo inside `careerpilot-v3/` at Phase 1. Trunk-based with feature branches. Logical, one-concern commits. Never commit `.env*`/secrets. `.env.example` committed.
- **Quality gates (run every phase):** backend `pytest`, `ruff check`, `mypy`(optional); web `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; then `git diff` review + phase report.
- **Phase discipline:** implement only the requested phase; after finishing: run tests/typecheck/build, report (Files changed / Tests / Build / Security considerations / Remaining issues), then stop. Never auto-advance.
- **Decision log:** record every architectural choice in `docs/DECISIONS.md` (why/problem/alternatives/chosen).
- **Reporting problems:** severity-tagged (CRITICAL/HIGH/MEDIUM/LOW); never claim something works without verification.

---

## 20. Phase-by-Phase Implementation Plan

Gated: each phase ends with the quality gates above and stops for review.

| Phase | Deliverable |
|---|---|
| 0 | ✅ This architecture plan (awaiting approval) |
| 1 | Repo scaffold: git init, npm workspaces root, `apps/web` (Next.js) + `apps/api` (FastAPI) skeleton, Tailwind, lint/typecheck/test/build wiring, `.env.example`, `.gitignore`, README |
| 2 | Supabase local + migrations (all tables, indexes), RLS policies, storage buckets/policies, Auth wiring (signup/login/logout/reset/session), protected routes, `/internal/health` |
| 3 | Profile + job/application/notification preferences: schema, API, UI, profile completeness computation |
| 4 | Job provider abstraction + ingestion pipeline skeleton (validate→normalize→eligibility→dedup→store) + internal sync endpoint |
| 5 | Greenhouse ingestion (unit/integration tested against fixtures) |
| 6 | Ashby ingestion (same fixtures approach). Note: also re-validate generic location normalization here |
| 7 | India location system + eligibility classifier + seed city data + tests (Bengaluru ✓ / Toronto ✗ / US-only remote ✗ / ambiguity conservative) |
| 8 | Jobs/internships public API: search (title/role/skill/company/city/state), filters, sort, pagination; backend-enforced India filtering |
| 9 | Deterministic matching engine + weight config + match breakdown + gap analysis (pure, tested) |
| 10 | Jobs/Internships UI: cards, search, filter chips, autocomplete (keyboard/mouse/mobile/loading/empty/debounce), infinite scroll |
| 11 | Opportunity detail + match explanation (deterministic breakdown + optional LLM phrasing), save button |
| 12 | Resume upload/storage/validation/extraction/parsing (original preserved, owner-scoped) |
| 13 | Resume analysis (heuristic checklist: contact, structure, skills, experience, projects, bullets, ATS-readability cues) |
| 14 | AI enhancement (provider abstraction, schema outputs, change review, no-fabrication policy) |
| 15 | Job-specific tailoring workflow (selected job → resume → match → enhancement → review → save) |
| 16 | Version management/list/download, lineage display |
| 17 | Application preparation: destinations model, application profiles, grounded drafting, sensitive-question policy |
| 18 | Supported application flows: CareerPilot flow or ATS-extension handoff (validate extension legality/scoping) + "continue application" |
| 19 | Application tracker: statuses, transitions, list/detail, notes, filters |
| 20 | Settings page, notifications (in-app), search autocomplete polish |
| 21 | Security hardening pass: full threat-matrix tests, load/rate review, HTML sanitizer edge cases |
| 22 | Full E2E (Playwright) across the product loop + acceptance checklist from spec §56 |
| 23 | Production readiness: docs, Dockerfile/Fly/Render config, observability, staging deploy |
| 24 | Production deployment with env/secret management, ingestion scheduling |

---

## 21. Definition of Done — Acceptance Mapping (spec §56)

Every numbered item maps to a phase + test. A checked item requires an automated test or verified manual check:

1. Sign up → P2 ✅ 2. Complete profile → P3 ✅ 3. Set Indian job preferences → P3 ✅ 4. Upload resume → P12 ✅ 5. View original resume → P12/P16 ✅ 6. Search Indian jobs → P8/P10 ✅ 7. Search Indian internships → P8/P10 ✅ 8. Filter by Indian city/work mode → P7-P10 ✅ 9. View job details → P11 ✅ 10. Deterministic match info → P9/P11 ✅ 11. Analyze resume → P13 ✅ 12. Enhance resume → P14 ✅ 13. Tailor to a job → P15 ✅ 14. Review changes → P14 ✅ 15. Save enhanced resume → P15 ✅ 16. Download enhanced resume → P16 ✅ 17. Prepare application → P17 ✅ 18. Apply via supported flow → P18 ✅ 19. Track application → P19 ✅ 20. Manage settings → P20 ✅

---

## 22. Open Decisions & Risks

| # | Item | Status |
|---|---|---|
| 1 | Deployment host for FastAPI (Render vs Railway vs Fly) | Decide at Phase 23; architecture is host-agnostic |
| 2 | Whether the browser extension is rebuilt/re-validated for Phase 18 | v2's extension is an external artifact; re-scope in Phase 18 |
| 3 | `uv` vs `pip` for Python env | Phase 1 detail |
| 4 | OpenRouter fallback model list | Phase 14 detail, config-driven |
| 5 | Full India city seed list size | Phase 7 detail (data-driven) |

**Priority order (product):** Correctness → Security → Usefulness → Maintainability → UX → Testing → Performance → Scalability.

**Explicitly out of scope:** certifications (any form), LinkedIn/Naukri/Indeed/Internshala/Foundit/Apna, worldwide jobs, payments, multi-agent architecture, social networking, recruiter marketplace, native mobile apps.