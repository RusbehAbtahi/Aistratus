#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_api.sh — Epic 2  (Edge / API Gateway) + 4 rich stories
#
# Location: 04_scripts/gh/create_epic_api.sh
# Usage:    bash 04_scripts/gh/create_epic_api.sh
#
# Prereqs  : gh auth login ✔  |  labels & milestone from GUI script exist
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create api   --description "API-layer work"             --color 8E44AD 2>/dev/null || true
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story --description "Individual user story"      --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_api.md <<'EOF'
**Epic Goal**

Stand up a secure, well-documented HTTP API layer that exposes three routes—`/infer`, `/stop`, and `/ping`—behind Amazon API Gateway (HTTP API).  
All requests must carry a valid JWT issued by Cognito; throttling protects back-end resources; structured access-logs land in CloudWatch.

**Why this matters**

The API is the *contract* between every current and future client (desktop, CLI, mobile app) and the cloud back-end.  
A rock-solid API surface gives front-end developers a stable target, lets DevOps set cost-control guardrails early, and surfaces abuse patterns in logs before they hurt our budget.

**Success / Acceptance**

1. A developer can run `curl -H "Authorization: Bearer <valid>" https://…/ping` and get `{"status":"ok"}`.  
2. Invalid or missing JWT returns `401 Unauthorized` in < 150 ms.  
3. Per-user throttle: 5 req/s bursts, 20 req/min sustained.  
4. CORS permits `http://localhost:*` for the desktop GUI.  
5. Access-logs in `/apigw/tl-fif` CloudWatch group include trace-id, caller-ip, latency, and HTTP status.  
EOF

# ---------- 2. Create epic and grab issue number -----------------------------
EPIC_URL=$(gh issue create \
  --title "Epic 2 – API Gateway layer" \
  --label epic,api \
  --body-file /tmp/epic_api.md \
  --milestone "$MILESTONE" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "✅  Epic #${EPIC_ID} created"

# ---------- 3. Helper to create richly-worded stories ------------------------
create_story () {
  local code="$1"; shift
  local title="$1"; shift
  local body="$1"
  echo "$body" > /tmp/story.md
  gh issue create \
    --title "${code}  ${title}" \
    --label api,story \
    --body-file /tmp/story.md \
    --milestone "$MILESTONE" \
    > /dev/null
  echo "   • ${code} created"
}

# ---------- 4. Story 1 – Route skeleton --------------------------------------
create_story "API-001" "Define & document HTTP routes" "
Belongs to **Epic #${EPIC_ID}**

**User Story**

*As a front-end integrator*  
I need a published OpenAPI 3 spec that declares `/infer`, `/stop`, and `/ping`
so I can generate type-safe client code and avoid guesswork.

**Why it matters**

Spelling mistakes in endpoints or payloads cascade into wasted debugging time.
An authoritative spec enforces a single source of truth and accelerates future client work.

**Acceptance Criteria**

1. `api/openapi.yaml` in Git is valid OpenAPI 3.1.  
2. Describes request/response JSON schemas with example payloads.  
3. GitHub Action runs `openapi-cli lint` and fails on spec errors.  
4. A generated HTML reference is available at  
   `https://RusbehAbtahi.github.io/Aistratus/api-spec/`."

# ---------- 5. Story 2 – JWT authorizer --------------------------------------
create_story "API-002" "JWT authorizer via Cognito" "
Belongs to **Epic #${EPIC_ID}**

**User Story**

*As a security-conscious architect*  
I want API Gateway to validate JWTs issued by our Cognito User Pool  
so that only authenticated users can invoke costly back-end resources.

**Why it matters**

Without upfront JWT validation, malicious actors could spin up EC2
and burn budget. Shifting auth left into API Gateway blocks abuse
before Lambda or EC2 incur cost.

**Acceptance Criteria**

1. Cognito user-pool authorizer configured with 60-min token TTL.  
2. Requests without `Authorization: Bearer …` header → **401**.  
3. Requests with expired or tampered token → **403**.  
4. Happy path adds `sub`, `email`, and `iat` claims as headers to Lambda.  
5. Postman collection demonstrates success & failure cases."

# ---------- 6. Story 3 – Throttle & CORS -------------------------------------
create_story "API-003" "Per-user throttling & CORS rules" "
Belongs to **Epic #${EPIC_ID}**

**User Story**

*As an ops engineer*  
I need sensible default throttling and CORS in place  
so that accidental GUI loops or rogue scripts cannot flood the system.

**Why it matters**

Redis queue and Lambda are cheap, but unconstrained floods can still
cause CPU spikes, noisy logs, and cascading latency.

**Acceptance Criteria**

1. Default burst: **5 req/s**; rate: **20 req/min** per token.  
2. Returned header `X-RateLimit-Limit` communicates limits.  
3. CORS allows `http://localhost:*` (desktop) and blocks other origins.  
4. Unit test simulates 6 rapid calls → 429 response on 6th."

# ---------- 7. Story 4 – Structured access-logs ------------------------------
create_story "API-004" "Structured JSON access-logs to CloudWatch" "
Belongs to **Epic #${EPIC_ID}**

**User Story**

*As a DevOps lead*  
I want every API call logged in JSON with trace-id, caller IP,
HTTP status, and latency so that I can debug incidents
and feed usage data into cost dashboards.

**Acceptance Criteria**

1. Logs land in group `/apigw/tl-fif` with retention 30 days.  
2. Each entry has keys: `requestId`, `ip`, `route`, `status`, `latencyMs`.  
3. Sample log verified via CloudWatch console and `aws logs tail`.  
4. CloudWatch Insights query file `queries/api_latency.cwi` committed."

echo "🎉  Epic 2 and its 4 detailed stories created"
