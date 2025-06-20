#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_queue.sh — Epic 4 (Redis Job Queue) + 4 detailed stories
#
# Prereqs : gh auth login ✔ • labels/milestone exist or are created here
# Usage   : bash 04_scripts/gh/create_epic_queue.sh
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create queue  --description "Redis queue work"                    --color F1C40F 2>/dev/null || true
gh label create epic   --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story  --description "Individual user story"               --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_queue.md <<'EOF'
**Epic Goal**

Deploy ElastiCache Redis 6.2 (cluster-mode off) as the high-speed job queue that buffers prompt requests between Lambda Router and the GPU worker.  
Jobs live exactly **5 minutes**—long enough to survive cold-boot latency but short enough to auto-purge orphans.

**Why this matters**

Redis is the “shock absorber” for burst traffic:  
* Lambda stays stateless and quick,  
* EC2 can wake on demand without losing requests, and  
* we avoid the cost/latency overhead of SQS long polling.  
A misconfigured queue would silently drop jobs or leak memory; a well-tuned one gives us instant, predictable throughput at <$0.03 hr.

**Success / Acceptance**

1. A developer can `redis-cli GET job:<uuid>` and see prompt JSON immediately after hitting `/infer`.  
2. Keys auto-expire ~300 s (±5 s); no manual cleanup needed.  
3. Security-group only allows traffic from Lambda SG and EC2 SG—nothing public.  
4. Connection string stored in SSM Parameter Store, *never* hard-coded.
EOF

# ---------- 2. Create epic & capture number ----------------------------------
EPIC_URL=$(gh issue create \
  --title "Epic 4 – Redis job queue" \
  --label epic,queue \
  --body-file /tmp/epic_queue.md \
  --milestone "$MILESTONE" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "✅  Epic #$EPIC_ID created"

# ---------- 3. Helper: create a story from stdin -----------------------------
make_story () {
  local code="$1"; shift
  local title="$1"; shift
  local tempfile
  tempfile=$(mktemp)

  # stdin → tmp file
  cat > "$tempfile"

  gh issue create \
    --title "${code}  ${title}" \
    --label queue,story \
    --body-file "$tempfile" \
    --milestone "$MILESTONE" >/dev/null

  rm "$tempfile"
  echo "   • ${code} created"
}

# ---------- 4. Story definitions --------------------------------------------
make_story RED-001 "Provision private t4g.small Redis cluster" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a DevOps engineer*  
I need a cost-effective Redis cluster running in a **private subnet**  
so that no public endpoint is exposed and latency to Lambda is < 1 ms.

**Details / Acceptance**

1. Launch single-node **t4g.small** in subnet `10.20.1.0/24`; cluster-mode off.  
2. Security-group **sg-redis** allows port 6379 **only** from **sg-lambda** and **sg-ec2-gpu**.  
3. Transit encryption disabled inside VPC (performance); *at-rest* encryption enabled.  
4. Terraform plan or console screenshot attached in PR.
EOF

make_story RED-002 "Job schema key job:{uuid} with TTL 300 s" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a back-end maintainer*  
I want each prompt stored at key `job:<uuid>` with a five-minute TTL  
so that orphaned jobs self-purge and memory usage stays bounded.

**Details / Acceptance**

1. Value JSON: `{prompt:str,idle:int,reply_s3:str,timestamp:int}`.  
2. Lambda sets `EX 300`; GPU worker never renews TTL.  
3. Unit test inserts → checks `TTL` ≈ 300 s → verifies key gone ≤ 310 s.
EOF

make_story RED-003 "Store Redis endpoint & auth in SSM" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a security auditor*  
I need the Redis connection URL saved in SSM Parameter Store  
so that credentials never leak into source code or AMIs.

**Details / Acceptance**

1. Parameter `/tinyllama/redis/url`, type *String*, created via IaC.  
2. Lambda role gets `ssm:GetParameter` for that ARN only.  
3. README includes `aws ssm put-parameter` example for dev onboarding.
EOF

make_story RED-004 "Add /queue-health route to ping Redis" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As an operator*  
I want a diagnostic `/queue-health` route that returns 200 when Redis replies  
so monitoring can detect queue outages early.

**Details / Acceptance**

1. Route wired in API Gateway; no Cognito—internal only.  
2. Lambda sends `PING`; returns `{"redis":"ok","latencyMs":<x>}`.  
3. Fails if latency > 200 ms or exception; CloudWatch alarm on 5 min failure.
EOF

echo "🎉  Epic 4 and four richly-described stories created"
