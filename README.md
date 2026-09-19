# CareerPilot India

AI-powered, India-first career platform: job/internship discovery, resume analysis
and AI enhancement, job-specific resume tailoring, application preparation and
tracking.

## Repository layout

- `frontend/` — Next.js 16 (App Router, TypeScript, Tailwind v4). Deployed to Vercel.
- `backend/` — FastAPI (Python 3.12). Deployed to Railway.
- `supabase/` — Supabase migrations, RLS policies, storage config (source of truth for DB).
- `e2e/` — Playwright product-loop tests.
- `docs/` — architecture, stack/setup, database, testing, decisions.

## Documentation

- Docs start here: `docs/ARCHITECTURE_PLAN.md`
- Tech stack, integrations and setup checklist: `docs/TECH_STACK_AND_SETUP.md`

## Getting started

See `docs/TECH_STACK_AND_SETUP.md` §12 (Local Development Setup). Copy
`.env.example` values into `backend/.env` and `frontend/.env.local`; never commit real
secrets.

## Quality gates

```bash
# backend
cd backend && ruff check . && pytest

# frontend
npm run typecheck && npm run lint && npm run test && npm run build
```

## Security

Service-role, AI, email and sync credentials are backend-only and never committed.
Enable RLS for every user-owned table via `supabase/` migrations. Job-provider HTML is
sanitized at write. AI output is schema-validated and never trusted blindly.