#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_lambda.sh — Epic 3 (Lambda Router v2) + 4 detailed stories
#
# Prereqs: gh auth login ✔   labels/milestone already exist or created here
# Usage  : bash 04_scripts/gh/create_epic_lambda.sh
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create lambda --description "Lambda router work"                 --color 2ECC71 2>/dev/null || true
gh label create epic   --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story  --description "Individual user story"              --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_lambda.md <<'EOF'
**Epic Goal**

Implement **`lambda_router_v2`**, a lightweight Python 3.12 Lambda (512 MB, 30 s timeout) that:

1. Verifies the Cognito-issued JWT on every request.  
2. If the GPU EC2 instance is *stopped*, starts it and returns a `"starting"` payload with an ETA.  
3. Otherwise, enqueues the prompt job into Redis with a 5-minute TTL.  
4. Responds instantly with a unique request-ID so the GUI can poll for results.  
5. Emits custom CloudWatch metrics: `Requests`, `ColdStarts`, `RedisEnqueueFail`, and `EC2Starts`.

**Why this matters**

The router is the **traffic director** for the entire TinyLlama stack.  
By keeping it **stateless, cheap, and tiny**, we isolate user authentication, queue integrity, and GPU start logic in one place, while avoiding EC2 cost unless real work is queued.  
Poorly-designed routers become hidden bottlenecks; a *well-instrumented* Lambda gives us real-time insight into load and latency for pennies.

**Success / Acceptance**

* Cold-start ≤ 500 ms; p95 warm latency ≤ 60 ms.  
* Valid prompt → Redis key `job:{uuid}` visible with TTL≈300 s.  
* Invalid JWT → 401 within 150 ms.  
* If GPU was stopped, Lambda publishes CloudWatch metric `EC2Starts=1`.  
* Unit-test suite in `01_src/tinyllama/orchestration/tests/` achieves ≥ 90 % coverage.
EOF

# ---------- 2. Create epic & capture number ----------------------------------
EPIC_URL=$(gh issue create \
  --title "Epic 3 – Lambda Router v2" \
  --label epic,lambda \
  --body-file /tmp/epic_lambda.md \
  --milestone "$MILESTONE" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "✅  Epic #$EPIC_ID created"

# ---------- 3. Helper: rich story creator ------------------------------------
make_story () {
  local code="$1"; shift
  local title="$1"; shift
  local body="$1"
  printf '%s\n' "$body" > /tmp/story.md
  gh issue create --title "${code}  ${title}" \
    --label lambda,story \
    --body-file /tmp/story.md \
    --milestone "$MILESTONE" >/dev/null
  echo "   • ${code} created"
}

# ---------- 4. Story definitions ---------------------------------------------
make_story "LAM-001" "JWT verification & payload schema guardrail" "
Belongs to **Epic #$EPIC_ID**

**User Story**

*As a security engineer*  
I need Lambda to reject any request that lacks a valid Cognito JWT or fails basic JSON-schema validation,  
so that untrusted input never reaches Redis or EC2.

**Details / Acceptance**

1. Use API Gateway's built-in JWT authorizer; re-verify signature in Lambda with `python-jose`.  
2. Schema: `{ prompt:str(max 6 kB), idle:int(1–30) }`.  
3. Failure path returns HTTP 400 (schema) or 401 (token).  
4. Unit tests cover token happy-path, expired token, tampered signature, and oversized prompt.
"

make_story "LAM-002" "Redis enqueue with 5-min TTL & UUID" "
Belongs to **Epic #$EPIC_ID**

**User Story**

*As the queue owner*  
I want each prompt enqueued at Redis key `job:{uuid}` with a 5-minute TTL  
so that orphaned jobs self-clean and workers can pop in O(1).

**Details / Acceptance**

1. UUID v4 generated per request; returned to caller.  
2. Redis value stores prompt, idle-timeout, S3 reply-path, and timestamp.  
3. On enqueue error, Lambda logs at ERROR and returns 503.  
4. Metric `RedisEnqueueFail` increments on failures.
"

make_story "LAM-003" "Start GPU EC2 instance when stopped" "
Belongs to **Epic #$EPIC_ID**

**User Story**

*As a cost-conscious user*  
I want Lambda to start the GPU node only when needed  
so that I don’t pay for idle time.

**Details / Acceptance**

1. Lambda calls `ec2:start_instances` with tag filter `env=tinyllama`.  
2. Returns `{ \"status\":\"starting\", \"eta\":90 }` immediately.  
3. Metric `EC2Starts` +1 on every cold-boot.  
4. Unit test mocks boto3 and asserts correct branch logic.
"

make_story "LAM-004" "Return immediate 202 with request-ID" "
Belongs to **Epic #$EPIC_ID**

**User Story**

*As a front-end developer*  
I need an immediate HTTP 202 response containing `{id:\"<uuid>\"}`  
so that the GUI can poll S3 without blocking the UI thread.

**Details / Acceptance**

1. Response body: `{ \"status\":\"queued\", \"id\":\"<uuid>\" }`.  
2. `X-Request-Id` header mirrors the UUID for tracing.  
3. Latency measured at p95 ≤ 60 ms (warm).  
4. Example cURL command documented in README.
"

echo "🎉  Epic 3 and four richly-described stories created"
