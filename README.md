# CareerPilot India

AI-powered, India-first career platform: job/internship discovery, resume analysis
and AI enhancement, job-specific resume tailoring, application preparation and
tracking.

## Repository layout

- `frontend/` — Next.js 16 (App Router, TypeScript, Tailwind v4). Runs locally with `npm run dev`; optionally deployable to Vercel or any Next.js-compatible host.
- `backend/` — FastAPI (Python 3.12). Runs locally with `uvicorn app.main:app --reload`; deployable by the new maintainer on any suitable Python host.
- `supabase/` — Supabase migrations, RLS policies, storage config (source of truth for DB).
- `e2e/` — Playwright product-loop tests.
- `docs/` — architecture, stack/setup, database, testing, decisions.

## Documentation

- Docs start here: `docs/ARCHITECTURE_PLAN.md`
- Tech stack, integrations and setup checklist: `docs/TECH_STACK_AND_SETUP.md`

## Getting started (local development — recommended)

1. Copy `.env.example` values into `backend/.env` (backend secrets) and `frontend/.env.local` (public values). Never commit real secrets.
2. Backend: `cd backend && pip install -r requirements.txt` (or `pip install -e .`) then `uvicorn app.main:app --reload --port 8000` — API at `http://localhost:8000/docs`.
3. Frontend: `npm install` then `npm run dev` in `frontend/` — app at `http://localhost:3000`.
4. Full setup, credentials, and service cards: `docs/TECH_STACK_AND_SETUP.md` §12 (Local Development Setup).

Deployment is handled by the new maintainer — see `docs/TECH_STACK_AND_SETUP.md` §14 for the generic architecture (Vercel optional for frontend, any Python host for backend).

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