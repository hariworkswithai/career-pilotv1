# CareerPilot India — Technical Stack, Integrations & Setup Checklist

Phase: 0 (Infrastructure & Architecture) — no application code written.
Verification: All endpoints/auth/limits below were checked against the providers' **current official documentation on 2026-09-17**. Re-verify each integration's docs immediately before implementing its phase.

**Revision note:** this document supersedes the earlier draft's repo layout (`apps/web` + `apps/api`) and deployment section. It now matches the finalized stack (below), per the Tech Stack & Integration Master Prompt.

---

## 1. Technology Stack (Complete)

| Layer | Technology | Version/pin rationale |
|---|---|---|
| Monorepo | Git repo at `Default Project\careerpilot-v3` | Single source of truth; no per-agent copies |
| Frontend | Next.js 16 (App Router), React 19, TypeScript 5, Tailwind CSS v4, ESLint | Current stable line already proven in this environment |
| Browser-side auth/session | `@supabase/ssr` + `@supabase/supabase-js` | Supabase-native; no custom password auth |
| API client | Generated TS client from backend OpenAPI | Single contract source of truth |
| Backend | Python 3.12+, FastAPI, Pydantic v2, Uvicorn | Async, typed, auto OpenAPI |
| Database / Auth / Storage | Supabase (PostgreSQL + Auth + Storage + RLS) | Managed; RLS-native |
| Job providers | httpx clients: Greenhouse + Ashby (provider abstraction) | Official public board APIs only |
| AI (app) | OpenRouter via `AIProvider` abstraction (OpenRouterProvider) | Model configurable via env; no hard-coded models |
| AI (dev/coding) | OmniRoute (dev-only routing: Claude Code/Codex/OpenCode → provider/model) | Not part of the production app |
| Email | Resend (backend only) | Official SDK |
| Error monitoring | Sentry (backend + frontend) | Separate DSNs/projects where appropriate |
| DNS/CDN | Cloudflare | Optional until deployment; no early complexity |
| Hosting | Frontend: Vercel (optional) or any Next.js host · Backend: any Python host (Railway, Render, Fly, etc.) | Choose at deployment time; local development requires no hosting |
| CI/CD | GitHub Actions | lint/typecheck/test/build + scheduled ingestion trigger |
| PDF/DOCX | `pypdf`, `pdfplumber`, `python-docx` | See §16 (licenses/security verified) |
| HTML sanitization | `nh3` (ammonia bindings) | Allowlist-based; job-provider HTML is untrusted |
| Testing | pytest (+TestClient) · Vitest · Playwright | §25 of master prompt |
| Python tooling | `uv` (env/deps), Ruff, `mypy` (optional) | Fast, modern |

Deliberately excluded (no Redis, Celery, Kafka, RabbitMQ, Elasticsearch, vector DB, MongoDB, AWS, Kubernetes, microservices). Modular monolith only.

---

## 2. External Service List (all integrations used or planned)

Supabase · Greenhouse · Ashby · OpenRouter · OmniRoute (dev) · Resend · Sentry · Vercel (optional, frontend) · Any Python host for backend · Cloudflare (optional, deploy-time) · GitHub Actions. Full per-service cards in §11.

---

## 3–4. API List & Endpoint List (FastAPI backend)

Base path: `https://<backend-host>/api/v1` (e.g. `http://localhost:8000` locally). FastAPI auto-serves `/docs` and `/openapi.json` (no duplicate hand-written API docs). The frontend calls only these endpoints; no direct DB access from the browser.

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/session` (verify token → session info) · `GET /auth/me` |
| Profile | `GET /profile` · `PUT /profile` · `DELETE /account` (full data deletion) |
| Preferences | `GET|PUT /job-preferences` · `GET|PUT /application-preferences` · `GET|PUT /notification-preferences` |
| Jobs | `GET /jobs` (search/filter/sort/page) |
| Internships | `GET /internships` (same query model; backend-enforced India eligibility) |
| Opportunities | `GET /opportunities/{id}` · `GET /opportunities/{id}/match` (auth) · `GET /opportunities/filters` · `GET /opportunities/{id}/similar` (later) |
| Search | `GET /search/suggestions?q=` (title/role/skill/city autocomplete) |
| Saved | `GET /saved` · `POST /saved` · `DELETE /saved/{id}` |
| Resumes | `POST /resumes` (multipart) · `GET /resumes` · `GET /resumes/{id}` · `POST /resumes/{id}/parse` · `POST /resumes/{id}/analyze` · `POST /resumes/{id}/enhance` · `POST /resumes/{id}/tailor` · `GET /resumes/{id}/versions` · `POST /resumes/{id}/versions` · `DELETE /resumes/{id}` |
| Resume versions | `GET /resumes/versions/{version_id}` · `DELETE /resumes/versions/{version_id}` |
| File downloads | `GET /files/resumes/{id}` · `GET /files/versions/{version_id}` (owner-only, signed URLs) |
| Applications | `GET /applications` · `POST /applications` · `GET /applications/{id}` · `PATCH /applications/{id}` (validated status transitions) · `POST /applications/{id}/prep` (grounded drafting) · `GET /applications/{id}/questions` (supported flows) · `DELETE /applications/{id}` |
| Notifications | `GET /notifications` · `POST /notifications/{id}/read` · `POST /notifications/read-all` |
| Settings | profile + preferences endpoints (above), `DELETE /account` |
| Internal | `GET /health` · `POST /internal/sync` (`x-internal-token`) · `GET /internal/sync/status` |

Frontend routes (Next.js): `/` landing, `/login`, `/signup`, `(app)` group → `/dashboard`, `/jobs`, `/internships`, `/opportunities/[id]`, `/resume`, `/resume/versions/[id]`, `/applications`, `/profile`, `/settings`.

---

## 5. Credential Requirements (name, purpose, where obtained, required?, exposure)

| Credential | Purpose | Where to obtain | Required | Exposure |
|---|---|---|---|---|
| `SUPABASE_URL` | Base URL to Supabase API/auth/storage | Supabase → Project Settings → API | Yes | Public (used by anon client + backend) |
| `SUPABASE_ANON_KEY` | Public API key (RLS-limited) | Supabase → API | Yes | Public by design (safe; RLS enforces ownership) |
| `SUPABASE_SERVICE_ROLE_KEY` | Bypass-RLS server operations (ingestion, file admin, deletions) | Supabase → API | Yes | **Backend-only. NEVER in frontend/GitHub/logs** |
| `SUPABASE_JWT_SECRET` | Local HS256 verification of user tokens (dev/tests) | Supabase → API → JWT Secret | Optional (prod uses JWKS) | Backend-only |
| `OPENROUTER_API_KEY` | AI calls (analysis/enhance/tailor) | https://openrouter.ai/settings/keys | Yes (for AI features) | Backend-only |
| `AI_MODEL` (+optional `AI_JSON_MODEL`) | Which OpenRouter model(s) to use | OpenRouter model catalog | Yes (defaults set) | Backend-only |
| `RESEND_API_KEY` | Transactional email | https://resend.com/api-keys | Yes (for email) | Backend-only |
| `SENTRY_DSN` | Error/trace capture | Sentry project → Settings → Client Keys (DSN) | Yes (prod); optional (dev) | DSN is **not a secret**; used in frontend + backend |
| `SENTRY_AUTH_TOKEN` | Source-map upload at build/CI | Sentry → Settings → Auth Tokens | Optional (CI only) | CI secrets |
| `INTERNAL_SYNC_TOKEN` | Guard the ingestion endpoint | Generate ourselves (e.g. `openssl rand -hex 32`) | Yes (prod); optional (dev) | Backend-only |
| `GREENHOUSE_SOURCES` | Board tokens to ingest | Each company's public Greenhouse job board URL | Yes (Greenhouse ph) | Backend-only (not secret) |
| `ASHBY_SOURCES` | Ashby job-board names to ingest | `jobs.ashbyhq.com/{name}` | Yes (Ashby ph) | Backend-only (not secret) |

Public-by-design values (`NEXT_PUBLIC_*`) are only those the browser genuinely needs. No real secrets are ever placed in `.env.example`.

---

## 6. Environment Variable List (actual `.env.example` contents — names, no values)

**Frontend (Vercel)** — public only where genuinely required:
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_APP_URL=            # e.g. https://careerpilot.example.com
NEXT_PUBLIC_API_BASE=           # FastAPI base URL (browser calls to backend)
SENTRY_DSN=                     # frontend Sentry project DSN
```

**Backend (Railway)** — all server-only:
```
ENVIRONMENT=                    # development | staging | production
LOG_LEVEL=
WEBAPP_URL=                     # frontend URL, for building links in emails/redirects
API_CORS_ORIGINS=

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=            # optional: local HS256 verify (dev/tests)

OPENROUTER_API_KEY=
AI_MODEL=                       # e.g. anthropic/claude-sonnet-latest (config-driven)
AI_JSON_MODEL=                  # optional; defaults to AI_MODEL
AI_MAX_TOKENS=
AI_TIMEOUT_MS=

RESEND_API_KEY=
RESEND_FROM_EMAIL=

SENTRY_DSN=                     # backend Sentry project DSN

INTERNAL_SYNC_TOKEN=

GREENHOUSE_SOURCES=             # comma-separated board tokens, e.g. acme,globex
ASHBY_SOURCES=                  # comma-separated board names, e.g. acme,globex

RESUME_MAX_MB=                  # default 10
RATE_LIMIT_PER_MINUTE=          # per-process default for AI/expense routes
SIGNED_URL_TTL_SECONDS=
```

**CI (GitHub Actions)** — secrets only: `SENTRY_AUTH_TOKEN`, plus any needed for vercel/railway auth tokens (platform-managed, not in repo).

---

## 7. Where Each Credential Is Obtained → covered in §5 table (single source of truth).

---

## 8. Required vs Optional → flagged in §5 (`Required` column) and §6 (comments).

---

## 9. Development vs Production Configuration

| Config | Development | Production |
|---|---|---|
| Supabase | A dedicated cloud project (dev) via `SUPABASE_URL` etc. (or optional `supabase start` local) | Managed production project; migrations via Supabase CLI only |
| Jobs sync | Manual trigger `POST /internal/sync` | GitHub Actions scheduled workflow → `POST /internal/sync` with token |
| AI | OpenRouter (real provider, low-cost models; `AI_MODEL` per dev) | OpenRouter; model set via env; budget limits |
| Email | Resend (test domain `onboarding@resend.dev` or sandbox) | Verified sending domain, `RESEND_FROM_EMAIL` |
| Error monitoring | Sentry optional / `traces_sample_rate=0` locally | Sentry on; PII collection off; no secrets/resumes |
| Secrets | Local `.env` / `.env.local` (gitignored) | Host env vars (e.g. Vercel for frontend, Railway/Render/etc. for backend), CI secrets |
| URL | `http://localhost:3000` (web) / `http://localhost:8000` (api) | `NEXT_PUBLIC_APP_URL`, Railway domain, `WEBAPP_URL` |

---

## 10. Repository Architecture

```
careerpilot-v3/
├── frontend/                    # Next.js 16
│   ├── app/ (auth + (app) route groups)  ├── src/components/{ui,domain}
│   ├── src/lib/api/generated/   # TS client generated from backend OpenAPI
│   ├── middleware.ts            # session refresh + route protection
│   └── package.json, next.config.ts, tsconfig.json, eslint.config.mjs, vitest.config.ts
├── backend/                     # FastAPI
│   ├── app/{core,db,schemas,routers,services/{ingestion,matching,locations,resumes,ai,applications}}
│   ├── tests/{unit,integration,api,security}
│   ├── pyproject.toml
│   └── Dockerfile               # Phase 23
├── supabase/                    # Supabase CLI config + forward-only migrations + RLS policies
├── e2e/                         # Playwright (root-level product-loop tests)
├── docs/                        # ARCHITECTURE_PLAN.md, TECH_STACK_AND_SETUP.md (this), DATABASE.md, ENV.md, DECISIONS.md, TESTING.md
├── .github/workflows/           # ci.yml, ingest-schedule.yml
├── .env.example                 # names only (committed)
├── .gitignore                   # .env*, node_modules, .next, __pycache__, etc.
├── package.json                 # root: workspace orchestration scripts (frontend tooling)
└── README.md
```

Reasoning: `frontend/` + `backend/` + `supabase/` matches the master prompt's recommended structure; `supabase/` owns 100% of schema/RLS so nothing is hand-mutated in production. This layout supersedes the earlier draft's `apps/web` + `apps/api` naming.

---

## 11. Per-Service Integration Cards (verified 2026-09-17)

### ✦ Supabase
- **SERVICE:** Supabase (PostgreSQL + Auth + Storage + RLS)
- **PURPOSE:** Database, authentication (email/password; future OAuth), private file buckets, row-level security
- **OFFICIAL WEBSITE:** https://supabase.com/
- **OFFICIAL DOCUMENTATION:** https://supabase.com/docs ; RLS: /docs/guides/database/row-level-security ; Storage: /docs/guides/storage
- **API BASE URL:** project-specific `https://<ref>.supabase.co` (+ `/auth/v1`, `/storage/v1`, `/rest/v1`, `/pg`).
- **ENDPOINTS (usage):** Auth signup/login/logout/reset via client SDK; storage signed URLs (backend `createSignedUrl`); PostgREST for row access.
- **AUTHENTICATION:** anon key (public, RLS-limited) for browser; service-role key (bypasses RLS) for backend only.
- **CREDENTIAL REQUIRED:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`. Get from project → Settings → API.
- **ENVIRONMENT VARIABLE:** see §6.
- **FREE/PAID:** Free tier (500 MB DB, 1 GB storage, 50k MAU auth); Pro ≈ $25/mo.
- **RATE LIMIT:** per-project usage limits on free tier; no hard rate limit docs for core API.
- **DEVELOPMENT/PRODUCTION:** same service, separate projects.
- **SECURITY NOTES:** RLS mandatory for all user-owned tables; storage private buckets + `storage.foldername(name)[1] = auth.uid()` policies; file paths keyed by user id; service-role key must remain backend-only.

### ✦ Greenhouse (Job Board API)
- **PURPOSE:** Job postings ingestion (India-eligible roles)
- **OFFICIAL WEBSITE:** https://greenhouse.io/
- **OFFICIAL DOCUMENTATION:** https://developers.greenhouse.io/job-board.html
- **API BASE URL:** `https://boards-api.greenhouse.io/v1/boards/{board_token}`
- **ENDPOINTS:** `GET /jobs` (optional `?content=true` for full post + departments + offices) · `GET /jobs/{id}` (optional `?questions=true&pay_transparency=true` for application fields + pay ranges) · `GET /offices`, `/departments`, `/sections` (optional enrichment). Job detail via `GET /jobs/{id}`; no separate "detail" API — use the retrieve-job endpoint.
- **AUTHENTICATION:** Public — no auth required for any GET endpoint. POST application (not used initially) needs Basic Auth (Base64 job-board API key), must be proxied server-side.
- **CREDENTIAL REQUIRED:** GET ingestion: none (only a board token in the URL path). No API key invented.
- **WHERE TO GET:** a board token is the company's public jobs slug, e.g. `https://boards.greenhouse.io/{board_token}`.
- **ENVIRONMENT VARIABLE:** `GREENHOUSE_SOURCES` (config list).
- **FREE/PAID:** Free.
- **RATE LIMIT:** Not published in the job-board docs → implement per-source throttling, retry with backoff, and caching; never hammer.
- **DEVELOPMENT/PRODUCTION:** same.
- **SECURITY NOTES:** location arrives as free text (`location.name`) → must be fed through India location normalization; HTML in `content` → sanitize at write; validate every record before storing.

### ✦ Ashby (Posting API)
- **PURPOSE:** Job postings ingestion (India-eligible roles)
- **OFFICIAL WEBSITE:** https://www.ashbyhq.com/
- **OFFICIAL DOCUMENTATION:** https://developers.ashbyhq.com/docs/public-job-posting-api
- **API BASE URL:** `https://api.ashbyhq.com`
- **ENDPOINTS:** `GET /posting-api/job-board/{jobBoardName}?includeCompensation={true/false}` — returns **all published postings in one response** (no server-side pagination/search/detail endpoints). Fields: `title`, `location`, `secondaryLocations`, `address.postalAddress.{addressLocality,addressRegion,addressCountry}`, `isRemote`, `workplaceType` (OnSite/Remote/Hybrid), `employmentType` (FullTime/PartTime/Intern/Contract/Temporary), `descriptionHtml`, `descriptionPlain`, `publishedAt`, `jobUrl`, `applyUrl`, `isListed`, `compensation` (with `includeCompensation=true`).
- **AUTHENTICATION:** Public — no credentials for public postings.
- **CREDENTIAL REQUIRED:** None (only the board name in the path). Documented future option: "Dedicated Partner Job Feeds" for licensed/opt-in feeds.
- **WHERE TO GET:** board name from `jobs.ashbyhq.com/{jobBoardName}`.
- **ENVIRONMENT VARIABLE:** `ASHBY_SOURCES` (config list).
- **FREE/PAID:** Free.
- **RATE LIMIT:** Not published → throttle per board; cache; single big payload per board (watch response size as job count grows).
- **DEVELOPMENT/PRODUCTION:** same.
- **SECURITY NOTES:** untrusted `descriptionHtml` → sanitize at write; location string + postalAddress → normalize; show only `isListed: true`; ignore "global/elsewhere" un-negated remote elsewhere scopes per eligibility rules.

### ✦ OpenRouter (AI — production)
- **PURPOSE:** Resume analysis, enhancement, job-specific tailoring, natural-language explanations
- **OFFICIAL WEBSITE:** https://openrouter.ai/
- **OFFICIAL DOCUMENTATION:** https://openrouter.ai/docs
- **API BASE URL:** `https://openrouter.ai/api/v1`
- **ENDPOINTS:** `POST /api/v1/chat/completions` (OpenAI-compatible; JSON mode/schema supported) · `GET /api/v1/models` (catalog). Optional headers: `HTTP-Referer`, `X-OpenRouter-Title`.
- **AUTHENTICATION:** `Authorization: Bearer <OPENROUTER_API_KEY>`.
- **CREDENTIAL REQUIRED:** `OPENROUTER_API_KEY` — https://openrouter.ai/settings/keys.
- **ENVIRONMENT VARIABLE:** `OPENROUTER_API_KEY`, `AI_MODEL`, `AI_JSON_MODEL`, `AI_MAX_TOKENS`, `AI_TIMEOUT_MS`.
- **FREE/PAID:** Free and paid models; pay-per-token. Keep budgets small; deterministic operations never call the LLM.
- **RATE LIMIT:** per-model/account rate limits vary by provider; check the models catalog.
- **DEVELOPMENT/PRODUCTION:** same provider; smaller/cheaper model in dev via env.
- **SECURITY NOTES:** backend-only; model always env-configured (never hard-coded); structured/schema outputs validated with Pydantic; untrusted resume/JD treated as data (prompt-injection hardening); no sensitive application answers sent to the provider; no full resume sent unless the specific operation requires it.

### ✦ OmniRoute (AI — development coding only)
- **PURPOSE:** Dev/coding-agent routing (Claude Code primary; Codex secondary; OpenCode available)
- **OFFICIAL WEBSITE:** N/A (local dev tool)
- **OFFICIAL DOCUMENTATION:** N/A — user-provided local endpoint
- **API BASE URL:** `http://localhost:20128`
- **ENDPOINTS:** none used by the product; routes coding-agent → provider/model
- **AUTHENTICATION:** local only.
- **CREDENTIAL REQUIRED:** none in production code.
- **ENVIRONMENT VARIABLE:** none in `.env.example` (dev-only tooling config).
- **FREE/PAID:** N/A.
- **RATE LIMIT:** N/A.
- **DEVELOPMENT/PRODUCTION:** development tool only — **not** the production backend, database, or frontend dependency.
- **SECURITY NOTES:** never referenced by application code; no credentials in the production frontend.

### ✦ Resend (Email)
- **PURPOSE:** verification/account emails, job & application notifications, system emails
- **OFFICIAL WEBSITE:** https://resend.com/
- **OFFICIAL DOCUMENTATION:** https://resend.com/docs
- **API BASE URL:** `https://api.resend.com`
- **ENDPOINTS:** `POST /emails` (send). Official Python SDK available (`resend`).
- **AUTHENTICATION:** `Authorization: Bearer re_...`; **User-Agent header required** (403 `1010` when missing; the SDK sends it automatically).
- **CREDENTIAL REQUIRED:** `RESEND_API_KEY` — https://resend.com/api-keys.
- **ENVIRONMENT VARIABLE:** `RESEND_API_KEY`, `RESEND_FROM_EMAIL`.
- **FREE/PAID:** Free tier (~3k emails/mo) → paid.
- **RATE LIMIT:** default 10 requests/sec per team; `429` when exceeded. Batch/queue notifications behind the backend.
- **DEVELOPMENT/PRODUCTION:** dev can use `onboarding@resend.dev` / sandbox; production uses a verified sending domain.
- **SECURITY NOTES:** backend-only; <1 password/token/sensitive application answers; no resume contents in email.

### ✦ Sentry (Error monitoring)
- **PURPOSE:** backend + frontend error/trace monitoring
- **OFFICIAL WEBSITE:** https://sentry.io/
- **OFFICIAL DOCUMENTATION:** https://docs.sentry.io/ (FastAPI: /platforms/python/integrations/fastapi · Next.js: /platforms/javascript/guides/nextjs)
- **API BASE URL:** per-project ingest DSN (`https://<key>@o<org>.ingest.sentry.io/<project>`).
- **ENDPOINTS:** SDK-driven (no custom code).
- **AUTHENTICATION:** DSN (public-safe); `SENTRY_AUTH_TOKEN` only for source-map upload in CI.
- **CREDENTIAL REQUIRED:** `SENTRY_DSN` (per app: frontend project + backend project).
- **ENVIRONMENT VARIABLE:** `SENTRY_DSN` (both apps), `SENTRY_AUTH_TOKEN` (CI).
- **FREE/PAID:** free/Dev tier; paid for volume.
- **RATE LIMIT:** quota-based per project.
- **DEVELOPMENT/PRODUCTION:** optional in dev (`traces` off); enabled in production.
- **SECURITY NOTES:** `send_default_pii=False`; never capture passwords, API/service-role keys, full resumes, or sensitive application answers; Sentry auto-filters keys named `auth`/`password`.

### ✦ Vercel (Frontend hosting — optional)
- **PURPOSE:** Next.js hosting/deploy (optional — any Next.js-compatible host works)
- **OFFICIAL WEBSITE/DOCS:** https://vercel.com / https://vercel.com/docs
- **CREDENTIALS:** none in repo; GitHub integration + env vars in project settings if used.
- **FREE/PAID:** Hobby free → Pro.
- **SECURITY NOTES:** `NEXT_PUBLIC_*` inlined at build → only genuinely public values use the prefix; all secrets stay server-side (backend env on whichever host is chosen).

### ✦ Backend hosting (FastAPI — choose at deploy time)
- **PURPOSE:** FastAPI hosting — local development uses `uvicorn app.main:app --reload`; production can be any suitable Python host (Railway, Render, Fly, etc.)
- **REFERENCE CONFIG:** start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (host injects `$PORT`). Use `backend/requirements.txt` or `backend/pyproject.toml` for dependencies. A `Dockerfile` is not required for local development.
- **CREDENTIALS:** env vars set in the chosen host's dashboard (secrets) — no repo copy.
- **SECURITY NOTES:** only the public HTTP service is exposed; secrets live in host env. Ingestion scheduled via GitHub Actions (not extra host infra).

### ✦ Cloudflare (DNS/CDN — deploy-time)
- **PURPOSE:** domain DNS (`domain → Vercel`, `api.domain → Railway`), optional WAF/CDN
- **OFFICIAL WEBSITE/DOCS:** https://www.cloudflare.com / https://developers.cloudflare.com
- **CREDENTIALS:** account-level; added at Phase 23/24 only.
- **FREE/PAID:** free plan adequate.
- **SECURITY NOTES:** not part of local development; avoid early complexity.

### ✦ GitHub Actions (CI/CD)
- **PURPOSE:** CI gates (frontend lint/typecheck/test, backend pytest/ruff, build) + scheduled ingestion trigger + deploy hooks (Vercel/Railway)
- **OFFICIAL DOCS:** https://docs.github.com/actions
- **CREDENTIALS:** repo secrets only (`SENTRY_AUTH_TOKEN`, platform tokens); scheduled workflow calls `POST /internal/sync` with `INTERNAL_SYNC_TOKEN`.
- **FREE/PAID:** free for public repos; billed minutes for private.

---

## 12. Local Development Setup (primary — no hosting required)

1. Clone/copy into `default-project/careerpilot-v3`.
2. `git init`, copy `.env.example` → `backend/.env` (backend secrets) and → `frontend/.env.local` (public values).
3. Create Supabase **dev** project (or `supabase start` for local; prefer cloud dev project for parity). Apply migrations from `supabase/migrations` via Supabase CLI.
4. Backend: `pip install -r backend/requirements.txt` (or `pip install -e backend/` / `uv sync` in `backend/`) → `uvicorn app.main:app --reload --port 8000` from `backend/` (OpenAPI at `http://localhost:8000/docs`).
5. Frontend: `npm install` → `npm run dev` in `frontend/` → `http://localhost:3000`.
6. Quality gates: `ruff check`, `pytest` (backend) and `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build` (frontend).
7. Trigger ingestion: `POST http://localhost:8000/api/v1/internal/sync` with `x-internal-token` (optional locally).
8. AI: use real OpenRouter key in dev (cheap models); no local model execution required.

Credentials setup: Supabase (project API keys + JWT secret), OpenRouter key, Resend key (dev), Sentry DSNs (optional), generate own `INTERNAL_SYNC_TOKEN`. No Railway/Render account required for local development.

---

## 13. CI/CD Architecture

- **PR CI (`ci.yml`):** frontend (typecheck → lint → test → build), backend (ruff → pytest), generated-client freshness check. Blocks merge on failure.
- **Deploy (optional, not required for local dev):** Frontend optionally via Vercel (GitHub-connected, preview + production); backend on any suitable Python host (Railway, Render, Fly, etc., auto-deploy from `backend/`). The new maintainer chooses the host.
- **Ingestion schedule (`ingest-schedule.yml` — optional):** cron → `POST {BACKEND_API_URL}/api/v1/internal/sync` with `INTERNAL_SYNC_TOKEN`. Can also be triggered manually locally.
- **Sentry source maps:** upload in frontend build via `SENTRY_AUTH_TOKEN` (CI secret) if Sentry is configured.
- **No secrets in workflows** beyond referenced GitHub secrets.

---

## 14. Deployment Architecture (generic — local-first)

Local: User → `localhost:3000` (Next.js) → `localhost:8000` (FastAPI) → Supabase (Postgres/Auth/Storage). AI: FastAPI → OpenRouter. Email: FastAPI → Resend. Monitoring: both apps → Sentry (if configured). Ingest: GitHub Actions cron or manual `POST /internal/sync` → providers → Supabase.

Production (example, maintainer's choice): User → Cloudflare (DNS, optional) → Vercel or any Next.js host (frontend) → any Python host for FastAPI (e.g. Railway, Render, Fly) → Supabase. Other combinations are supported — the architecture is host-agnostic.

---

## 15. Security Architecture (summary — full matrix in ARCHITECTURE_PLAN.md §15)

RLS on every user-owned table; service-role key backend-only; owner checks re-enforced in backend code; upload validation by magic bytes + extension + size (+ timeout out); job HTML sanitized at write with `nh3` allowlist; token verification via JWKS (JWT secret for dev); rate limiting on auth/AI routes; per-process limiter initially; headers (CSP/HSTS/XFO/nosniff/Referrer/Permissions) at deploy; prompt-injection hardening; schema-validated AI output; no fabrication; secrets never in frontend/repo/logs.

---

## 16. Dependencies / Package Lists

**Backend (`backend/pyproject.toml`):**
- Runtime: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `httpx`, `python-multipart`, `PyJWT`, `pypdf`, `pdfplumber`, `python-docx`, `nh3`, `resend`, `sentry-sdk`
- Dev/test: `pytest`, `pytest-asyncio`, `ruff`, `mypy` (optional)

**Frontend (`frontend/package.json`):**
- Runtime: `next`, `react`, `react-dom`, `@supabase/ssr`, `@supabase/supabase-js`, `zod`, `clsx` (or `tailwind-merge`), `lucide-react`, `@sentry/nextjs` (optional)
- Dev/test: `typescript`, `tailwindcss`, `@tailwindcss/postcss`, `eslint`, `eslint-config-next`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `@types/*`, `openapi-typescript`
- Root/e2e: `@playwright/test`

**Library choices (verified 2026-09-17):**
- `pypdf` v latest — BSD-3, pure Python, Production/Stable, active (release Sep 2026). PDF validation + basic extraction.
- `pdfplumber` v0.11.x — MIT (built on MIT `pdfminer.six`), active (Jun 2026). Robust text extraction for machine-generated PDFs.
- `python-docx` v1.2.0 — MIT, stable; **maintenance is inactive** (no release in >12mo) but no known security issues in the current version. Acceptable for DOCX text extraction; monitor and swap (e.g., `mammoth`) if needed.
- PyMuPDF: **rejected** — AGPL-3.0/commercial license creates AGPL obligations for a commercial SAAS; pypdf/pdfplumber cover the need.
- `nh3` (ammonia bindings) — fast, maintained, allowlist sanitization for job-provider HTML.

---

## 17. Integration Order

1. Supabase project + schema + RLS + storage → 2. FastAPI base (config, auth verify, health, CORS) → 3. Next base (auth pages, middleware, layout) → 4. Greenhouse (re-verify docs → fixtures → provider → ingest) → 5. Ashby (same) → 6. India location normalization + eligibility → 7. Jobs/internships API → 8. Matching engine → 9. Profile + preferences + settings → 10. Resumes (upload/storage/parse) → 11. Analysis → 12. Enhance/tailor (OpenRouter + guardrails) → 13. Applications → 14. Notifications (Resend) → 15. Sentry both apps → 16. CI/CD → 17. Cloudflare + production deploy. (This is the implementation order in the master prompt §34; phases gated at each step.)

---

## 18. Risks & Limitations

| Risk | Severity | Mitigation |
|---|---|---|
| Provider payload/field drift | HIGH | Typed Pydantic models; fixtures in tests; re-verify docs per phase; tolerant field mapping |
| Greenhouse has no published job-board rate limit | MED | Throttle per source, retry w/ backoff, cache, run syncs on schedule not in-request |
| Ashby returns full board in one payload (no pagination) | MED | Per-board fetch, size monitoring; consider partner feed later |
| `python-docx` maintenance inactive | LOW | Extraction-only use; fallback to `mammoth`; pinned version |
| AI cost/fabrication | MED | Deterministic-first; structured outputs; budgets; no-fabrication validation |
| India-eligibility false negatives | LOW | By design (conservative per spec); precision over recall; reason logged |
| Resend 10 rps team limit | LOW | Backend queue/batch; retry on 429 |
| OpenRouter model availability varies | LOW | Model via env; provider abstraction; retries |
| Free-tier limits (Supabase/Vercel/Railway) at launch | LOW | Monitor usage; upgrade only when needed |

---

## 19. Out of Scope (explicitly, per master prompt)

Certifications (any form) · LinkedIn/Naukri/Indeed/Internshala/Foundit/Apna · worldwide job support · payments · Redis/Celery/Kafka/RabbitMQ/Elasticsearch/vector DB · microservices · native mobile apps · custom password auth.