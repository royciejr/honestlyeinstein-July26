# Maths Practice Platform

Adaptive maths practice for children aged 8–11 (UK Year 4–6 / US Grade 3–5, plus UK 11+ stretch).

Core loop: a parent photographs a child's completed paper maths work. A vision pipeline reads it,
marks it per-question, tags errors against a skill graph, and updates the child's mastery state.
Weak skills trigger batch-generated drill questions. Progression is organised as "worlds"
(modules) of skills; mastering a module unlocks the next.

**Status: Phase 1 — infrastructure scaffold.** Marking and generation Lambdas are stubs behind
feature flags; the plumbing is real end-to-end (S3 → EventBridge → Lambda → HMAC-signed API →
Postgres, and a Step Functions generate/verify/symcheck skeleton).

## Layout

| Path | What |
|---|---|
| `apps/api` | FastAPI backend (Render). Async SQLAlchemy 2 + Alembic, Clerk auth, HMAC internal endpoints. |
| `apps/web` | Next.js 14 App Router PWA (Vercel). Clerk login, child profiles, module map, photo upload. |
| `infra/` | AWS CDK (TypeScript), region `ap-southeast-1`. Upload pipeline, Step Functions generation pipeline, budget alert. |
| `content/` | Human-editable skill graph (`graph.yaml`) and papers. Loaded by `scripts/load_*.py`. |
| `scripts/` | Content loaders (validate → idempotent upsert) and demo helpers. |
| `docs/` | `RUNBOOK.md` (deploy everything from scratch), `PATTERNS.md` (conventions reused from the reference project). |
| `DECISIONS.md` | One-line log of every non-obvious choice and the rejected alternative. |

## Quickstart (local)

```bash
# API
cd apps/api
uv venv && uv pip install -e '.[dev]'          # or: pip install -e '.[dev]'
cp .env.example .env                            # fill DATABASE_URL, Clerk vars
alembic upgrade head
uvicorn app.main:app --reload

# Content
python scripts/load_graph.py content/graph.yaml
python scripts/load_paper.py content/papers/example-arithmetic-a

# Web
cd apps/web
npm install && cp .env.example .env.local       # fill Clerk keys + API URL
npm run dev
```

Full deploy instructions (Neon, Render, Vercel, Clerk, CDK): `docs/RUNBOOK.md`.
