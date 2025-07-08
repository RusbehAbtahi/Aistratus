#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_infra002_global_ssm.sh — Creates issue INFRA-002
# Prereqs : gh auth login ✔, repo cloned, run from repo root
# Usage   : bash 04_scripts/gh/create_infra002_global_ssm.sh
# ------------------------------------------------------------------
set -euo pipefail

# ---------- 0.  Labels ------------------------------------------------
echo "==> Ensuring labels"
gh label create infra      --description "Infrastructure / platform work"      --color 5319e7 2>/dev/null || true
gh label create terraform  --description "Terraform IaC change"                --color a2eeef 2>/dev/null || true
gh label create backend    --description "Backend / shared-infra change"       --color 0e8a16 2>/dev/null || true
gh label create "size:S-2" --description "½-day ticket"                        --color fef2c0 2>/dev/null || true

# ---------- 1.  Milestone ---------------------------------------------
echo "==> Ensuring milestone"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api "repos/$REPO/milestones" \
  -f title="Intermediate Stage" \
  -f state="open" \
  -F description="All intermediate-stage work (GUI + on-demand GPU + global backend)" \
  > /dev/null 2>&1 || true   # Ignore ‘already exists’

# ---------- 2.  Create the issue --------------------------------------
echo "==> Creating INFRA-002 – Global ID registry via SSM Parameter Store"

cat > /tmp/infra002_body.md <<'EOF'
### 🎯 Goal
Move **all hard-coded AWS resource IDs** (Cognito, VPC, S3, etc.) into a single,
authoritative SSM Parameter path `/tinyllama/global/*` *in the **default**
Terraform workspace only*.  
All other workspaces (`dev`, `feature/*`, `prod`) **read** those parameters
as data sources, avoiding circular references.

### 📂 New / changed files
| File                                                            | Purpose |
|-----------------------------------------------------------------|---------|
| `terraform/10_global_backend/modules/ssm_params/main.tf`        | *Writes* global IDs (default workspace only). |
| `terraform/10_global_backend/outputs.tf`                        | Collects IDs from existing modules. |
| `terraform/10_global_backend/workspace_data.tf`                 | Reads the same parameters for non-default workspaces. |
| `terraform/variables.tf`                                        | Adds `publish_ssm` flag (default **true** in default WS, **false** elsewhere). |
| `terraform/locals_ids.tf`                                       | Centralises parameter names to avoid typos. |
| IAM snippets in `modules/auth/*` & `modules/networking/*`       | Adds minimal **read-only** `ssm:GetParameter` permission to Lambda, EC2 & GitHub OIDC roles. |

### ✅ Acceptance criteria
1. `terraform apply` in **default** WS writes all IDs under `/tinyllama/global/...`.
2. Switching to any other workspace and running `terraform plan` shows **no diff**.
3. Every Lambda / EC2 that previously used a hard-coded ID now calls  
   `aws ssm get-parameter --name $PARAM --with-decryption --query 'Parameter.Value' --output text`.
4. New *public* env-file **.env_public** (committed) sets `TLFIF_ENV=public`; existing private `.env` stays unchanged.
5. CI pipeline passes with zero manual secrets.

### ⛔ Out of scope
* No refactor of existing modules beyond the single `ssm:GetParameter` addition.
* No parameter **writes** outside the default workspace.

### 🔧 Implementation check-list
- [ ] Add the new Terraform files (see PR content).
- [ ] `terraform fmt`, `validate`, `plan` (default & dev workspaces).
- [ ] Update IAM snippets (PR **must request existing files** first).
- [ ] Replace explicit IDs in Python (`config.py`, `auth_client.py`, etc.) with SSM look-ups – separate PR after TF merges.
- [ ] Add `.env_public` and teach all CLI scripts to source it *if present*.

### 🔎 References
RFC #27 “Option 1 SSM Global IDs”, Epics2-7 detailed, audit 4.5 patch.
EOF

gh issue create \
  --title "INFRA-002 – Global ID registry via SSM Parameter Store (Option 1)" \
  --body-file /tmp/infra002_body.md \
  --label infra,terraform,backend,"size:S-2" \
  --milestone "Intermediate Stage"

echo "==> INFRA-002 created ✔"
