# Setup status — paused 2026-08-29

Deliberately scaled down mid-setup. Nothing is incurring cost: AWS has **no deployed
stacks** (both Deploy AWS runs failed at the OIDC credentials step, before CDK ran),
and Neon/Clerk/GitHub are on free tiers. Check Render wasn't left on a paid instance —
otherwise dormant cost is £0/month.

## Done ✅
- Neon project (`neondb`, ap-southeast-1): schema migrated (Alembic `0001`) and example
  content loaded via the **DB migrate + load content** workflow (run #2, green). DoD #1 met.
- GitHub Actions secrets/variables set: `DATABASE_URL`, `INTERNAL_HMAC_SECRET`,
  `BUDGET_ALERT_EMAIL`, `AWS_DEPLOY_ROLE_ARN`.
- Clerk application created ("honestly einstein"), Access mode → Restricted; keys +
  Frontend API URL + admin user id collected (held by the owner, not in the repo).
- AWS IAM: GitHub OIDC identity provider + `maths-github-deploy` role
  (AdministratorAccess, trust-scoped to `repo:royciejr/honestlyeinstein-July26:*`,
  account 290046508409).

## Blocked / not started ⏸
- **Deploy AWS workflow fails** with `Not authorized to perform sts:AssumeRoleWithWebIdentity`
  (runs #1 and #2). Trust policy was replaced with a known-good version; the remaining
  suspect is the identity provider's **Audiences** list — it must contain exactly
  `sts.amazonaws.com` (IAM → Identity providers → token.actions.githubusercontent.com →
  Add audience). Fix that, then re-run **Deploy AWS** with the *bootstrap* box ticked.
- Render service: not created (or if created during setup, verify it's on the Free
  instance or suspended).
- Vercel project: not created.

## Resume checklist
1. IAM → Identity providers → confirm/add audience `sts.amazonaws.com`.
2. Actions → **Deploy AWS** (stacks: all, bootstrap: ✓) → copy `UploadBucketName` output.
3. Render: create per RUNBOOK §3 (branch `claude/maths-platform-phase-1-4twal5`, root
   `apps/api`, Docker, `/healthz`), env vars incl. `S3_UPLOAD_BUCKET` from step 2; then
   set GitHub variables `API_BASE_URL` (+ later `WEB_ORIGINS`) and re-run **Deploy AWS**
   so the Lambdas learn the real API URL.
4. Vercel: create per RUNBOOK §4; add its URL to Render `CORS_ALLOWED_ORIGINS` and the
   `WEB_ORIGINS` variable; re-run **Deploy AWS** (bucket CORS).
5. Prove DoD: **Run generation pipeline** ×2 (normal + force_disagreement), photo upload
   at /upload, `next-drill` returns a question.
