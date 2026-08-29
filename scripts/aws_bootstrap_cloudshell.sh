#!/usr/bin/env bash
# One-time AWS bootstrap, designed to be pasted into AWS CloudShell — the
# browser terminal inside the AWS console (works from a phone). Your AWS
# credentials never leave AWS: this sets up keyless deploys where GitHub
# Actions assumes an IAM role via OIDC federation.
#
# What it does (safe to re-run):
#   1. Creates the GitHub OIDC identity provider (if missing)
#   2. Creates/updates the `maths-github-deploy` role, trusted ONLY for
#      workflows in the $REPO repository
#   3. CDK-bootstraps ap-southeast-1 (app) and us-east-1 (budget stack)
#   4. Generates INTERNAL_HMAC_SECRET and prints the values to store in GitHub
#
# Usage in CloudShell:
#   curl -sO https://raw.githubusercontent.com/royciejr/honestlyeinstein-July26/claude/maths-platform-phase-1-4twal5/scripts/aws_bootstrap_cloudshell.sh
#   bash aws_bootstrap_cloudshell.sh
set -euo pipefail

REPO="royciejr/honestlyeinstein-July26"
ROLE_NAME="maths-github-deploy"
REGION_APP="ap-southeast-1"
REGION_BUDGET="us-east-1"

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "→ AWS account: $ACCOUNT"

# 1. GitHub OIDC provider (one per account). Thumbprint is required by the
# API but ignored by AWS for GitHub's provider since 2023.
PROVIDER_ARN="arn:aws:iam::${ACCOUNT}:oidc-provider/token.actions.githubusercontent.com"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
  echo "→ OIDC provider already exists"
else
  echo "→ creating GitHub OIDC provider"
  aws iam create-open-id-connect-provider \
    --url "https://token.actions.githubusercontent.com" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" >/dev/null
fi

# 2. Deploy role, trusted only for this repo's workflows.
TRUST=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "${PROVIDER_ARN}" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
        "StringLike": { "token.actions.githubusercontent.com:sub": "repo:${REPO}:*" }
      }
    }
  ]
}
EOF
)
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "→ role exists; refreshing trust policy"
  aws iam update-assume-role-policy --role-name "$ROLE_NAME" --policy-document "$TRUST"
else
  echo "→ creating role $ROLE_NAME"
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST" \
    --description "GitHub Actions OIDC deploys for ${REPO} (CDK)" >/dev/null
fi
# Solo-project simplicity: admin on this role; the trust policy above is the
# perimeter (only this repo's workflows can assume it). Tighten later if the
# project grows operators.
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE_NAME}"

# 3. CDK bootstrap (CloudShell ships Node.js; cdk is fetched by npx).
echo "→ cdk bootstrap ${REGION_APP} + ${REGION_BUDGET} (a few minutes on first run)"
npx --yes aws-cdk@2 bootstrap "aws://${ACCOUNT}/${REGION_APP}" "aws://${ACCOUNT}/${REGION_BUDGET}"

# 4. Internal HMAC secret (shared by the API on Render and the Lambdas).
HMAC_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cat <<EOF

============================================================
DONE. Now store these in GitHub — repo Settings → Secrets and
variables → Actions (both tabs work fine from a phone browser):

  Variables tab:
    AWS_DEPLOY_ROLE_ARN = ${ROLE_ARN}
    BUDGET_ALERT_EMAIL  = <your email>
    API_BASE_URL        = <Render URL, once it exists>
    WEB_ORIGINS         = <Vercel URL>,http://localhost:3000

  Secrets tab:
    INTERNAL_HMAC_SECRET = ${HMAC_SECRET}
      (ALSO set this same value as INTERNAL_HMAC_SECRET in the
       Render service's Environment tab)
    DATABASE_URL         = <direct Neon connection string>

Then everything deploys from GitHub → Actions:
  "Deploy AWS", "DB migrate + load content", "Run generation pipeline".
============================================================
EOF
