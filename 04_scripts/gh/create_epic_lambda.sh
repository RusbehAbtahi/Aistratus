#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_lambda.sh — Creates Epic 3 (Lambda Router v2) tickets
# Requires: gh auth login ✔, run from repo root
# Usage:    bash 04_scripts/gh/create_epic_lambda.sh
# ------------------------------------------------------------------
set -euo pipefail

# ---------- 0. Labels ------------------------------------------------
echo "==> Ensuring labels"
gh label create epic     --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create lambda   --description "Serverless router work"                --color BFDADC 2>/dev/null || true
gh label create story    --description "Individual user story"                --color 7057FF 2>/dev/null || true

# ---------- 1. Milestone ---------------------------------------------
echo "==> Ensuring milestone"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api "repos/$REPO/milestones" \
  -f title="Intermediate Stage" \
  -f state="open" \
  -F description="All intermediate-stage work (GUI + on-demand GPU inference)" \
  >/dev/null 2>&1 || true

# ---------- 2. Epic ---------------------------------------------------
echo "==> Creating Epic 3 – Lambda Router v2"
cat > /tmp/epic_lam.md <<'EOF'
**Epic Goal**

Build a **stateless, 512 MB, Python 3.12 Lambda Router** that:
1. Accepts authenticated requests from API Gateway (`/infer`, `/stop`).
2. Validates JWT + payload, enqueues jobs into Redis, and cold-boots GPU as needed.
3. Responds in ≤ 60 ms warm, emitting `X-Request-Id` and trace headers.

**Why it matters**

The router is the orchestration brain that converts authenticated user prompts into cost-safe GPU workloads, enforcing security, rate-limit, and observability boundaries.

**Acceptance**

* Tickets **LAM-001 … LAM-005** are all ✔ *Done* with clarified criteria (see individual issues).
* GUI → API → Lambda smoke test passes: valid login, prompt, 202 queue, `X-Request-Id` trace.
* p95 warm latency ≤ 60 ms (X-Ray), p50 cold-start ≤ 2.0 s (reported in CloudWatch).
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 3 – Lambda Router v2" \
  --label epic,lambda \
  --body-file /tmp/epic_lam.md \
  --milestone "Intermediate Stage" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "Epic #$EPIC_ID created"

# ---------- 3. Helper -------------------------------------------------
create_story () {
  local id="$1"; shift
  local title="$1"; shift
  local body="$1"
  printf '%s\n' "$body" > /tmp/body.md
  gh issue create \
    --title "$id  $title" \
    --label lambda,story \
    --body-file /tmp/body.md \
    --milestone "Intermediate Stage" \
    >/dev/null
  echo "  • $id created"
}

# ---------- 4. Stories ------------------------------------------------
echo "==> Creating Lambda stories"

create_story "LAM-001" "Router Skeleton & Pytest Harness" \
"Belongs to **Epic #$EPIC_ID**

Context: Lay initial structure and a deliberately failing test (TDD).

**Acceptance Criteria**
- [ ] Scaffold \`router/handler.py\`, \`tests/router_test.py\` (pytest-asyncio).
- [ ] Add **\`.env.dev\` template** (DATA_BUCKET, COGNITO_APP_CLIENT_ID, LOCAL_JWKS_PATH).
- [ ] Promote/re-export \`make_token\` helper from API package for reuse.
- [ ] \`make lambda-package\` target in **Makefile** builds ZIP (CI uses it).
- [ ] \`sam local invoke\` documented to pick up \`.env.dev\`.
- [ ] CI must fail on placeholder test until LAM-002 passes.

<details><summary>Definition of Ready / Done</summary>

- **Ready**: labels set, ADR (if any) merged, failing test reproduced locally.  
- **Done**: main branch green, VERSION bumped, ADR updated if structure changed.
</details>"

create_story "LAM-002" "JWT & Input Schema Validation" \
"Belongs to **Epic #$EPIC_ID**

Context: Reject bad input _before_ incurring Redis or EC2 cost.

**Acceptance Criteria**
- [ ] Re-use **\`verify_jwt\`** util from API; share code, avoid divergence.
- [ ] Implement **lazy JWKS reload** to prevent \"unknown kid\" races.
- [ ] Validate body: \`prompt ≤ 6 kB\`, optional \`idle ≤ 30\`.
- [ ] Error map: missing/invalid JWT → 401, bad schema → 400, unknown kid / expired / aud-mismatch → 403.
- [ ] Unit tests cover: valid, expired, tampered, wrong aud, unknown kid (5 cases).
- [ ] Coverage ≥ 90 % on router package.

**Warnings / Lessons from API-002**
- Insert \`COGNITO_APP_CLIENT_ID\` via env **everywhere** (pytest, SAM, CI) or tests will silently pass with dummy aud.  
- Make sure JWKS cache refreshes between tests; seed \`LOCAL_JWKS_PATH\` from \`02_tests/api/data/mock_jwks.json\`.

<details><summary>Definition of Ready / Done</summary></details>"

create_story "LAM-003" "Redis Enqueue with 5-Minute TTL" \
"Belongs to **Epic #$EPIC_ID**

Context: Queue must self-clean to avoid memory leaks.

**Acceptance Criteria**
- [ ] Generate UUID v4 → key \`job:{uuid}\`, TTL 300 s.
- [ ] Job JSON: \`prompt\`, \`idle\`, \`reply_s3\`, \`timestamp\`.
- [ ] On Redis error → 503, metric \`RedisEnqueueFail=1\`.
- [ ] Integration test (`fakeredis`) asserts TTL 295-305 s.
- [ ] Emit CloudWatch metric \`JobsEnqueued\`.

**Notes**
- Use connection pool for speed; unit test patch must supply fake pool.  
- Duplicate UUID collision is statistically impossible; no extra lookup needed."

create_story "LAM-004" "GPU Cold-Boot Logic" \
"Belongs to **Epic #$EPIC_ID**

Context: Router decides when to pay for GPU.

**Acceptance Criteria**
- [ ] Detect EC2 state: \`stopped → pending → running\`; no duplicate start in \"pending\".
- [ ] Tag filter: \`env=tinyllama\`, fail if >1 node (explicit error 500).
- [ ] Call \`start_instances\`, return 202 body: \`{\"status\":\"starting\",\"eta\":90}\`.
- [ ] Metric \`EC2Starts\` +1 per cold boot.
- [ ] boto3 unit tests stub three branches (stopped/pending/running).

**Warnings**
- Incorrect handling of \"pending\" led to race in early API JWT cache; replicate tests for state transitions."

create_story "LAM-005" "Immediate 202 + Request-ID Reply" \
"Belongs to **Epic #$EPIC_ID**

Context: GUI must remain responsive while job runs.

**Acceptance Criteria**
- [ ] Warm path p95 latency ≤ 60 ms (AWS X-Ray).
- [ ] Response: \`{\"status\":\"queued\",\"id\":\"<uuid>\"}\`, header \`X-Request-Id:<uuid>\`.
- [ ] X-Ray segment name must equal UUID for quick Insights queries.
- [ ] Canary Lambda logs sample payloads for 24 h.
- [ ] Add GUI-API-LAM headless smoke test: login → prompt → 202, ensure \`X-Request-Id\` echoed.

**Definition of Done**
- GUI headless smoke test passes in CI.
- Dashboard shows p95 latency < 60 ms after five warm invocations."

echo "==> Lambda epic and five stories DONE"
