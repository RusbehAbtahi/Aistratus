#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_api.sh — Creates Epic 2 API stories, labels, milestone
# Prereqs: gh auth login ✔, repo cloned, run from repo root
# Usage:   bash 04_scripts/gh/create_epic_api.sh
# ------------------------------------------------------------------
set -euo pipefail

# ---------- 0.  Labels ------------------------------------------------
echo "==> Ensuring labels"
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create api   --description "Edge API work"                        --color E99695 2>/dev/null || true
gh label create story --description "Individual user story"                --color 7057FF 2>/dev/null || true

# ---------- 1.  Milestone ---------------------------------------------
echo "==> Ensuring milestone"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api "repos/$REPO/milestones" \
  -f title="Intermediate Stage" \
  -f state="open" \
  -F description="All intermediate-stage work (GUI + on-demand GPU inference)" \
  > /dev/null 2>&1 || true

# ---------- 2.  Epic ---------------------------------------------------
echo "==> Creating Epic 2 – Secure Edge API Gateway"
cat > /tmp/epic_api.md <<'EOF'
**Epic Goal**

Expose a single, authenticated HTTP API surface (`/infer`, `/stop`, `/ping`) that blocks bad traffic, enforces cost-safe throttling, and produces audit-grade logs.

**Why it matters**

API Gateway is the security and observability gate for all user and internal access.

**Acceptance**

– Stories API-001…API-005 all *Done*  
– OpenAPI contract, end-to-end security tests, and cost metrics signed off
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 2 – Secure Edge API Gateway" \
  --label epic,api \
  --body-file /tmp/epic_api.md \
  --milestone "Intermediate Stage" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "Epic #$EPIC_ID created"

# ---------- 3.  Helper to spawn stories --------------------------------
create_story () {
  local id="$1" ; shift
  local title="$1" ; shift
  local body="$1"
  printf '%s\n' "$body" > /tmp/body.md
  gh issue create \
    --title "$id  $title" \
    --label api,story \
    --body-file /tmp/body.md \
    --milestone "Intermediate Stage" \
    > /dev/null
  echo "  • $id created"
}

# ---------- 4.  API stories --------------------------------------------

echo "==> Creating API stories"

create_story "API-001" "API Skeleton & Test Harness" \
"Belongs to **Epic #$EPIC_ID**

Context: Set up repo folders, pytest infrastructure, and a failing integration test to enforce TDD.

**Acceptance Criteria:**
- Create package structure: \`api/\` with empty \`routes.py\`, \`tests/\` with pytest scaffold.
- GitHub Action runs \`pytest\` and fails on placeholder test.
- Include minimal \`openapi.yaml\` with empty path definitions.
- README documents local \`uvicorn\` mock run.
- Assign ownership via GitHub \`CODEOWNERS\` file (API PRs routed to back-end team)."

create_story "API-002" "JWT Authorizer via Cognito" \
"Belongs to **Epic #$EPIC_ID**

Context: All edge calls must prove identity without warming downstream services.

**Acceptance Criteria:**
- Requests lacking valid \`Authorization\` header return **401 within 150 ms**.
- Expired/invalid JWTs return **403**; valid tokens forward claims.
- API Gateway caches JWKs ≤ 10 min.
- Postman tests show happy path + three negative cases.
- Contract test in CI hits a mocked JWKS endpoint.
- Clearly document the Cognito setup process explicitly in README (\`api/README.md\`) to avoid configuration confusion later."

create_story "API-003" "Per-User Throttling & CORS Enforcement" \
"Belongs to **Epic #$EPIC_ID**

Context: Prevent runaway GUI loops and hostile scripts.

**Acceptance Criteria:**
- Burst limit **5 req/s**, sustained **20 req/min** per Cognito \`sub\`.
- Exceeding limits returns **429** with proper \`Retry-After\` header.
- CORS allows \`http://localhost:*\`; all other origins blocked.
- Smoke test sends 6 rapid calls; last must return 429.
- Emit metric \`RateLimitBreaches\` to CloudWatch."

create_story "API-004" "Structured JSON Access Logging" \
"Belongs to **Epic #$EPIC_ID**

Context: Enable rapid troubleshooting through structured, machine-parseable logs.

**Acceptance Criteria:**
- JSON log format: \`requestId\`, \`ip\`, \`route\`, \`status\`, \`latencyMs\`.
- Logs stored in CloudWatch group \`/apigw/tl-fif\` with 30-day retention.
- CloudWatch Insights query saved as \`queries/api_latency.cwi\`.
- CI asserts log fields via AWS SDK stub.
- p95 latency alarm (≥300 ms 5 min) created and enabled."

create_story "API-005" "Health Check Route (/ping)" \
"Belongs to **Epic #$EPIC_ID**

Context: Lightweight endpoint for automated uptime checks.

**Acceptance Criteria:**
- \`GET /ping\` returns \`{\"status\":\"ok\"}\` within 100 ms.
- Route is JWT-exempt, requires VPC-only source CIDR 10.20.0.0/22.
- Terraform outputs URL for external health-checkers (e.g., Pingdom).
- Synthetic test in CloudWatch Synthetics checks every minute.
- Failure 3/5 iterations triggers PagerDuty alert."

echo "==> API epic and five stories DONE"
