# Patterns reused from `capitulation-project-Apr26`

The reference repo was studied before writing any code here. This is the honest ledger of
what was copied, what was deliberately upgraded, and what was consciously skipped.

## Reused as-is

| Pattern | Reference source | Here |
|---|---|---|
| Clerk JWT verification: RS256 against the issuer's JWKS via `PyJWT[crypto]` + cached `PyJWKClient`, no Clerk SDK | `api/auth.py`, `CLERK_SETUP.md` | `apps/api/app/auth.py` |
| `CLERK_AUTH_DISABLED=1` local-dev bypass; unset secrets always fail closed, never open | `api/auth.py` | `auth.py`, `routers/internal.py` |
| Per-router auth via `dependencies=[Depends(...)]` at include time | `api/main.py` | `apps/api/app/main.py` |
| CORS origins as a comma-separated env var, parsed to a list | `api/main.py` | `config.py` |
| `python:3.12-slim` image, single uvicorn worker, `$PORT` from Render | `Dockerfile` | `apps/api/Dockerfile` |
| Clerk frontend: `ClerkProvider` in root layout + `export const dynamic = "force-dynamic"` (publishable key isn't available at prerender) | `frontend/src/app/layout.tsx` | `apps/web/src/app/layout.tsx` |
| `clerkMiddleware` + `createRouteMatcher` public allowlist, explicit `redirectToSignIn` (302, not `auth.protect()`'s 404) | `frontend/src/middleware.ts` | `apps/web/src/middleware.ts` |
| Next 14.2.x + `@clerk/nextjs` 6.x combo (Clerk v7 requires Next 15) | `frontend/package.json` | `apps/web/package.json` |
| `.env.example` discipline: every var documented with where to find its value | `.env.example` | both apps |
| Exact `==` dependency pins | `requirements.txt` | `apps/api/pyproject.toml` |
| psycopg v3 binary wheel against Neon (no libpq headers needed on Render) | `requirements.txt` comments | via SQLAlchemy `postgresql+psycopg://` |

## Upgraded (reference had a weaker version)

| Here | Reference had | Why changed |
|---|---|---|
| `pydantic-settings` central `Settings` class (`config.py`) | ad-hoc `os.environ.get` scattered everywhere | one typed, documented config surface |
| SQLAlchemy 2 async + Alembic migrations | raw psycopg + `CREATE TABLE IF NOT EXISTS` executed in a startup thread | real schema history; migrations reviewed in PRs, run deliberately (see RUNBOOK) |
| HMAC-signed internal endpoints: `t=<ts>,v1=<hmac-sha256>`, `hmac.compare_digest`, ±300s replay window | plaintext shared secret compared with `==` | constant-time compare, replay protection |
| CI: ruff + mypy + pytest, eslint + tsc + vitest, `cdk synth` | syntax-check only (`compileall`/`ast.parse`) | this repo starts with real gates |
| Token passing: small typed `fetch` wrapper (`lib/api.ts` `useApi()`) | axios instance + interceptor component | same idea, one dependency fewer |

## Consciously skipped (with the trigger that would revive them)

- **`MALLOC_ARENA_MAX=2` self-re-exec** (their `api/main.py:7-79`): their OOM killer was
  glibc arenas from heavy thread-pool churn. This API spawns no thread pools. If Render RSS
  creeps toward 512MB under load, port that block first — it cut their RSS 30-50%.
- **DuckDB local fallback / dual-backend shim**: we standardise on Postgres everywhere
  (Neon free tier locally too). One backend, one dialect.
- **On-boot schema init + backfill threads**: replaced by Alembic; nothing schema-shaped
  happens at boot. `/healthz` is deliberately DB-free like theirs (Render health checks
  must not recycle the service during a Neon cold start).
- **Neon `-pooler` host rewrite + IPv4 `hostaddr` pinning** (`core/pg.py`): real fixes for
  real incidents (stale pooled reads; Render→Neon IPv6 breakage). Not ported pre-emptively;
  documented in RUNBOOK troubleshooting with a pointer to their implementation.
- **46 cron workflows curling the backend**: nothing scheduled exists yet. When batch
  generation needs a schedule, prefer EventBridge Scheduler → Step Functions over
  GitHub-Actions-cron-hits-API.
