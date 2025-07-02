#!/usr/bin/env bash
# create_epic_infra.sh — Bootstrap backend & base VPC
set -euo pipefail

# ---------- 0. Labels ------------------------------------------------
echo "==> Ensuring labels"
gh label create epic     --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create infra    --description "Terraform baseline work"               --color F9D0C4 2>/dev/null || true
gh label create story    --description "Individual user story"                --color 7057FF 2>/dev/null || true

# ---------- 1. Milestone ---------------------------------------------
echo "==> Ensuring milestone"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api "repos/$REPO/milestones" \
  -f title="Bootstrap Stage" \
  -f state="open" \
  -F description="Remote state + base VPC foundation" \
  >/dev/null 2>&1 || true

# ---------- 2. Epic ---------------------------------------------------
echo "==> Creating Epic INFRA-000 – Terraform Backend & Base VPC"
cat > /tmp/epic_infra.md <<'EOF'
**Epic Goal**

Provide a reproducible Terraform foundation:
1. Remote-state backend (S3 bucket `tinnyllama-terraform-state` + DynamoDB lock table `terraform_locks` in eu-central-1).
2. Green-field VPC (10.20.0.0/22) with public subnet, two private subnets, IGW, NAT-GW, and VPC interface endpoints (S3, SSM, CloudWatch).

**Why it matters**

All future Terraform modules (API, Lambda, Redis, CostOps) depend on a managed backend and network substrate. Without this baseline, later tickets cannot plan or apply safely.

**Acceptance**

* Story **INF-001** delivered and merged.
* `terraform apply` for `00_bootstrap_state` succeeds locally; state moves to S3 and locks with DynamoDB.
* `terraform apply` for `10_global_backend` succeeds; VPC & networking resources are visible in AWS and importable by downstream modules.
EOF

EPIC_URL=$(gh issue create \
  --title "INFRA-000 – Terraform Backend & Base VPC" \
  --label epic,infra \
  --body-file /tmp/epic_infra.md \
  --milestone "Bootstrap Stage" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "Epic #$EPIC_ID created"

# ---------- 3. Story --------------------------------------------------
cat > /tmp/story.md <<'EOF'
Belongs to **Epic #'"$EPIC_ID"'**

**Acceptance Criteria**
- [ ] Commit `terraform/00_bootstrap_state` module that creates S3 bucket `tinnyllama-terraform-state` (versioning + SSE) and DynamoDB table `terraform_locks` (PAY_PER_REQUEST).
- [ ] Apply module once locally using the default local backend; verify remote state files physically in S3 and lock entry in DynamoDB.
- [ ] Commit `terraform/10_global_backend` root module with backend block pointing to the new bucket/table and provider for eu-central-1.
- [ ] Add child module `modules/networking` that provisions VPC 10.20.0.0/22, subnets (10.20.0.0/24 public, 10.20.1.0/24 private-a, 10.20.2.0/24 private-b), IGW, NAT-GW, route tables, and VPC endpoints for S3, SSM, CloudWatch.
- [ ] `terraform apply` of `10_global_backend` completes with no manual console actions.
- [ ] Outputs expose VPC ID, subnet IDs, and NAT-GW ID for downstream modules.
EOF

gh issue create \
  --title "INF-001  Bootstrap remote state & base VPC" \
  --label infra,story \
  --body-file /tmp/story.md \
  --milestone "Bootstrap Stage" \
  >/dev/null
echo "  • INF-001 created"
