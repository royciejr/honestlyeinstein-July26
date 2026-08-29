# RUNBOOK — deploy everything from scratch

Every step to go from a fresh clone to the full Phase 1 system, and the demo that proves
it. Nothing deploys automatically; CI only lints/tests/synths.

## The moving parts and how values flow between them

```
Clerk (auth)          Neon (Postgres 16)         AWS ap-southeast-1
  │ issuer URL             │ DATABASE_URL           ├─ S3 upload bucket ──► EventBridge ──► marker Lambda ─┐
  ▼                        ▼                        ├─ Step Functions (gen/verify/symcheck/writer) ────────┤ HMAC POST
Vercel (Next.js) ──JWT──► Render (FastAPI) ◄────────┴──────────────── /internal/* ◄────────────────────────┘
        └── presigned PUT ──────────────────────────► S3
```

Values you'll copy between consoles:

| Value | Produced by | Consumed by |
|---|---|---|
| `DATABASE_URL` | Neon | Render env, your shell (migrations/loaders) |
| `CLERK_JWT_ISSUER` (Frontend API URL) | Clerk | Render env |
| Clerk publishable + secret keys | Clerk | Vercel env |
| Your Clerk user id (`user_...`) | Clerk → Users | Render env `ADMIN_CLERK_USER_IDS` |
| `INTERNAL_HMAC_SECRET` (you generate) | you | Render env AND shell when running `cdk deploy` |
| Render URL | Render | `infra/cdk.json` `apiBaseUrl` context, Vercel env `NEXT_PUBLIC_API_BASE_URL` |
| Vercel URL | Vercel | Render env `CORS_ALLOWED_ORIGINS`, `infra/cdk.json` `webOrigins` |
| `UploadBucketName` output | `cdk deploy` | Render env `S3_UPLOAD_BUCKET` |

## Phone-only operation (recommended)

Everything in this runbook can be driven without a laptop. One-time setup:

1. **AWS** — open **CloudShell** in the AWS console (works in a mobile browser) and run
   `scripts/aws_bootstrap_cloudshell.sh` (a curl+bash two-liner is in the script header).
   It creates a keyless GitHub→AWS deploy role (OIDC — your AWS credentials never leave
   AWS), CDK-bootstraps both regions, generates `INTERNAL_HMAC_SECRET`, and prints every
   value to store in GitHub.
2. **GitHub** — repo Settings → Secrets and variables → Actions: add what the script
   printed (`AWS_DEPLOY_ROLE_ARN`, `BUDGET_ALERT_EMAIL`, secret `INTERNAL_HMAC_SECRET`),
   plus secret `DATABASE_URL` and variables `API_BASE_URL` / `WEB_ORIGINS` as those URLs
   come into existence below.
3. **Neon** — create the project in the console and paste `docs/sql/0001_initial_schema.sql`
   into its SQL editor (zero local tooling).
4. **Clerk / Render / Vercel** — dashboard clicks per sections 2–4; all fine in a mobile
   browser. Render and Vercel auto-deploy the connected branch on push, so merging a PR
   in the GitHub app *is* the deploy button for the API and the web app.

After that, recurring operations are taps in the repo's **Actions** tab:

| Button | What it does |
|---|---|
| **Deploy AWS** | `cdk deploy` through the OIDC role; stack outputs (bucket name) land in the run summary |
| **DB migrate + load content** | Alembic + graph/paper loaders against Neon — GitHub runners can reach port 5432, so content edits load with a tap |
| **Run generation pipeline** | one Step Functions execution; the happy path seeds a verified template (powers next-drill) |

Suggested first-run order: CloudShell script → GitHub values → Neon (+ **DB migrate +
load content**) → Clerk → Render → Vercel → set `API_BASE_URL`/`WEB_ORIGINS` variables →
**Deploy AWS** → copy the bucket name into Render's `S3_UPLOAD_BUCKET` → **Run generation
pipeline** → upload a photo from your phone at /upload.

None of the workflows fire on push — they are manual buttons only.

## 0. Prerequisites

- Accounts: Neon, Clerk, Render, Vercel, AWS (with billing alerts allowed).
- Phone path: nothing to install — CloudShell + the Actions buttons cover it.
- Laptop path additionally needs: Python 3.11+, Node 20+, `uv` (or plain pip), and for
  AWS the CLI + CDK bootstrap (skip this block if the CloudShell script already ran —
  it does the bootstrap):

```bash
# If `aws` is missing:
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install
aws configure   # your own credentials — never share/store them in the repo

# One-time per account+region (CDK v2):
cd infra && npm install
npx cdk bootstrap aws://<ACCOUNT_ID>/ap-southeast-1
npx cdk bootstrap aws://<ACCOUNT_ID>/us-east-1     # budget stack lives here
```

- Generate the internal HMAC secret once and keep it somewhere safe:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 1. Neon (Postgres)

1. Create a project (region: AWS ap-southeast-1 to match everything else), database `maths`.
2. Copy the **direct** connection string — host must NOT contain `-pooler` — with
   `?sslmode=require`.
3. Create the schema. Two equivalent routes:
   - **Zero-tooling**: paste `docs/sql/0001_initial_schema.sql` into the Neon console
     SQL editor and run it (it also stamps `alembic_version`, so alembic stays in sync).
   - **Or via Alembic** (and then load the example content):

```bash
cd apps/api
uv venv && uv pip install -e '.[dev]'        # or: python -m venv .venv && pip install -e '.[dev]'
source .venv/bin/activate
export DATABASE_URL='postgresql://...neon.tech/maths?sslmode=require'
alembic upgrade head

cd ../..
python scripts/load_graph.py content/graph.yaml
python scripts/load_paper.py content/papers/example-arithmetic-a
```

   (No laptop? Actions → **DB migrate + load content** runs the migration and both
   loaders from a GitHub runner using the `DATABASE_URL` secret.)
4. One-time sanity check that the hand-written initial migration matches the models
   (should print no changes): `cd apps/api && alembic revision --autogenerate -m probe`
   — inspect that the generated file is empty, then delete it.

**This completes Definition-of-Done #1** (graph.yaml loads into Neon).

## 2. Clerk

1. Create an application. **Configure → Restrictions → Sign-up mode → Restricted** (no
   public signups). Add yourself as a user (invitation or manual).
2. Note the **Frontend API URL** (API Keys → Show API URLs), e.g.
   `https://<slug>.clerk.accounts.dev` → this is `CLERK_JWT_ISSUER`.
3. Note the publishable key (`pk_...`) and secret key (`sk_...`) for Vercel.
4. Users → your user → copy the User ID (`user_...`) for `ADMIN_CLERK_USER_IDS`.

## 3. Render (FastAPI)

1. New → Web Service → connect this repo.
   - Root Directory: `apps/api`. Runtime: **Docker** (it finds `apps/api/Dockerfile`).
   - Instance: the 512MB tier is fine (single uvicorn worker by design).
   - Health check path: `/healthz`.
2. Environment tab — set (see `apps/api/.env.example` for commentary):
   `DATABASE_URL`, `CLERK_JWT_ISSUER`, `ADMIN_CLERK_USER_IDS`, `INTERNAL_HMAC_SECRET`,
   `CORS_ALLOWED_ORIGINS=http://localhost:3000` (add the Vercel URL after step 4),
   `AWS_REGION=ap-southeast-1`. Leave `S3_UPLOAD_BUCKET` empty until step 5.
3. Deploy; check `https://<render-url>/healthz` returns `{"status":"ok"}`.

Redeploys: push to the connected branch, or Manual Deploy in the dashboard.

## 4. Vercel (Next.js)

1. Import the repo → Framework: Next.js → **Root Directory: `apps/web`**.
2. Env vars (all environments): `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`,
   `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-in`,
   `NEXT_PUBLIC_API_BASE_URL=https://<render-url>`.
3. Deploy. Then close the loop:
   - Render → `CORS_ALLOWED_ORIGINS=https://<vercel-url>,http://localhost:3000` (redeploy).
   - Clerk → add the Vercel domain (Domains / allowed origins).
4. Sign in on the Vercel URL, add a child on /children, see the module map on /.

**This completes DoD #4** (deployed app, Clerk login, child profiles + module map from DB).

## 5. AWS (CDK) — upload pipeline, generation pipeline, budget

**Phone path**: set the `API_BASE_URL` / `WEB_ORIGINS` variables in GitHub, then tap
Actions → **Deploy AWS** (needs the CloudShell bootstrap done once). Outputs appear in
the run summary. The laptop equivalent:

```bash
cd infra
npm install

# apiBaseUrl must be the public Render URL so Lambdas can call /internal/*:
#   edit cdk.json context { "apiBaseUrl": "https://<render-url>",
#                           "webOrigins": ["https://<vercel-url>", "http://localhost:3000"],
#                           "budgetEmail": "you@example.com" }
# (or pass -c apiBaseUrl=... -c budgetEmail=... on the command line)

export INTERNAL_HMAC_SECRET='<the same secret you gave Render>'
npx cdk deploy MathsUploadPipeline MathsGenerationPipeline MathsBudget
```

Outputs to wire up:
- `MathsUploadPipeline.UploadBucketName` → Render env `S3_UPLOAD_BUCKET` → redeploy API.
- `MathsGenerationPipeline.StateMachineArn` → used in the demo below.

## 6. Prove the Definition of Done

**DoD #2 — photo → S3 → EventBridge → marker Lambda → Postgres.**
Via the UI: /upload → choose child → upload any JPEG → Refresh until status flips
`pending → marked`. Or from a shell (works against local or Render API):

```bash
# Local API needs CLERK_AUTH_DISABLED=1 in apps/api/.env; against Render pass --token
python scripts/demo_upload.py --api-base https://<render-url> --token '<clerk JWT>'
```

(Grab a JWT quickly: sign in on the Vercel app → DevTools console →
`await window.Clerk.session.getToken()`.)

Then confirm in the DB (or the /upload page): `uploads.status='marked'` and
`uploads.marking_json` populated, plus `child_state` rows for the child.

**DoD #3 — Step Functions runs end-to-end with stubs.**

Phone path: Actions → **Run generation pipeline** — run it once normally (seeds a
verified template) and once with *force the human-review branch* ticked (seeds a
review_queue row). The laptop equivalent:

```bash
ARN=$(aws stepfunctions list-state-machines --region ap-southeast-1 \
      --query "stateMachines[?name=='maths-template-generation'].stateMachineArn" --output text)

# Happy path -> writer inserts a *verified* template via the API:
aws stepfunctions start-execution --region ap-southeast-1 --state-machine-arn "$ARN" \
  --input '{"skill_slug": "times-tables-to-12"}'

# Disagreement path -> review_queue row:
aws stepfunctions start-execution --region ap-southeast-1 --state-machine-arn "$ARN" \
  --input '{"skill_slug": "times-tables-to-12", "force_disagreement": true}'

aws stepfunctions list-executions --region ap-southeast-1 --state-machine-arn "$ARN" --max-items 2
```

Both executions should end `SUCCEEDED`. The happy path also makes
`GET /children/<id>/next-drill` return a real instantiated question (that's the drill
stub working), and the disagreement path shows up in `GET /admin/review-queue` (as your
admin user).

**DoD #5** is this file. **DoD #1/#4** were completed in steps 1 and 4.

## 7. Local development

```bash
# API (terminal 1)
cd apps/api && source .venv/bin/activate
cp .env.example .env    # set DATABASE_URL; set CLERK_AUTH_DISABLED=1 for tokenless dev
uvicorn app.main:app --reload

# Web (terminal 2)
cd apps/web && npm install
cp .env.example .env.local   # real Clerk keys; NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

Tests/lints exactly as CI runs them, from the repo root:

```bash
source apps/api/.venv/bin/activate
ruff check apps/api scripts && ruff format --check apps/api scripts
mypy apps/api/app scripts
pytest apps/api/tests -q
python scripts/load_graph.py content/graph.yaml --check
cd apps/web && npm run lint && npm run typecheck && npm run test -- --run
cd ../../infra && npm run typecheck && INTERNAL_HMAC_SECRET=x npx cdk synth -q
```

## 8. Teardown

```bash
cd infra
npx cdk destroy MathsGenerationPipeline MathsBudget
# Empty the bucket first (only if you truly mean to delete children's photos):
aws s3 rm s3://<UploadBucketName> --recursive
npx cdk destroy MathsUploadPipeline
```

Render/Vercel/Neon/Clerk: delete from their dashboards.

## Troubleshooting

- **API 503 "DATABASE_URL is not configured"** — env var missing on Render, or you're
  hitting a fresh deploy before env changes propagated.
- **Slow first request after idle** — Neon scale-to-zero cold start; `pool_pre_ping` +
  retry absorb it. Keep `/healthz` as the Render health check (it never touches the DB).
- **Stale reads or hangs against Neon** — make sure the host has no `-pooler`. The
  reference project also had to pin IPv4 (`hostaddr`) for Render→Neon; if connections
  hang, port `core/pg.py:_conninfo()` from `capitulation-project-Apr26`.
- **Browser PUT to S3 fails with CORS** — the Vercel URL isn't in the bucket's
  `webOrigins` context; update `infra/cdk.json` and `cdk deploy MathsUploadPipeline`.
- **Marker Lambda logs 401 from the API** — `INTERNAL_HMAC_SECRET` mismatch between
  Render and the value exported when you ran `cdk deploy`.
- **Render memory creep toward 512MB** — see `docs/PATTERNS.md` "Consciously skipped":
  port the reference's `MALLOC_ARENA_MAX` re-exec block first.
