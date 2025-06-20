#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_ec2.sh — Epic 5 (GPU EC2 inference) + 4 rich stories
#
# Prereqs : gh auth login ✔ • labels & milestone exist or created here
# Usage   : bash 04_scripts/gh/create_epic_ec2.sh
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create ec2   --description "EC2 GPU work"                 --color E67E22 2>/dev/null || true
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story --description "Individual user story"        --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_ec2.md <<'EOF'
**Epic Goal**

Stand up a **hibernated g4dn.xlarge** instance pre-baked with TinyLlama weights and vLLM.  
Cold-boot (stop → ready) must deliver the **first token ≤ 90 s** end-to-end.

**Why this matters**

GPU time is our single biggest cost driver.  
By hibernating the node while retaining model weights on an encrypted gp3 cache, we pay only €0.04-0.05 per five-minute session yet still deliver sub-two-minute round-trip UX.

**Success / Acceptance**

* AMI baked via EC2 Image Builder; version tracked in SSM param.  
* Full boot timeline measured with stopwatch ≤ 90 s.  
* SSH port 22 closed; management **SSM-only**.  
* `watcher.py` consumes Redis job, calls vLLM, uploads JSON to S3.  
* Local idle-timer thread stops instance after chosen idle minutes.
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 5 – EC2 GPU inference node" \
  --label epic,ec2 \
  --body-file /tmp/epic_ec2.md \
  --milestone "$MILESTONE" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "✅  Epic #$EPIC_ID created"

# ---------- 2. helper ---------------------------------------------------------
make_story () {
  local code="$1"; shift
  local title="$1"; shift
  local body_file
  body_file=$(mktemp)
  cat > "$body_file"
  gh issue create --title "${code}  ${title}" \
    --label ec2,story --milestone "$MILESTONE" \
    --body-file "$body_file" >/dev/null
  rm "$body_file"
  echo "   • ${code} created"
}

# ---------- 3. Story EC2-001  -------------------------------------------------
make_story EC2-001 "AMI bake with vLLM + TinyLlama weights" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a platform engineer*  
I need a repeatable Image Builder pipeline that produces an AMI
already containing CUDA 12, vLLM 0.4.2, and the `tinyllama-1.1B-chat.gguf` weights
so that cold boots skip package installs and model download time.

**Details / Acceptance**

1. Image Builder recipe installs Ubuntu 22.04, CUDA 12, Python 3.10, vLLM, weights.  
2. Root volume: gp3 100 GiB, 3 000 IOPS.  
3. Final AMI tag `tl-fif:gpu-node` and version stamp `YYYYMMDD-hhmm`.  
4. Pipeline triggered by CodeBuild; manual approval before AMI promotion.  
5. Build cost and duration captured in PR comment.
EOF

# ---------- 4. Story EC2-002  -------------------------------------------------
make_story EC2-002 "watcher.py: pop Redis job & upload S3 reply" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As the queue consumer*  
I want a daemon `watcher.py` to pop jobs from Redis, stream
inference via vLLM, and upload the JSON result to `s3://tl-fif-responses/<uuid>.json`
so that the GUI can fetch answers without polling the EC2 instance directly.

**Details / Acceptance**

1. Runs under **supervisord**; reconnects on Redis error with back-off.  
2. Calls `vllm.engine.async_generate` for lower latency.  
3. Writes `/tmp/<uuid>.json` first, then uploads to S3 (server-side encrypted).  
4. Deletes local temp file on success; logs error & re-queues on failure.  
5. Functional test uses `fakeredis` and local MinIO.
EOF

# ---------- 5. Story EC2-003  -------------------------------------------------
make_story EC2-003 "Idle-timer self-stops instance" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a budget owner*  
I need an idle-timer thread that stops the instance after *N* minutes
(with N provided by the GUI) so that forgotten sessions never burn money.

**Details / Acceptance**

1. Idle-timer resets on every successful inference.  
2. When counter reaches zero, calls IMDS-signed `ec2:StopInstances` on self.  
3. Timer value defaults to 5 min, overridable 1-30 via JSON payload.  
4. Unit test mocks boto3 and asserts stop called after synthetic idle period.  
5. CloudWatch metric `AutoStops` increments.
EOF

# ---------- 6. Story EC2-004  -------------------------------------------------
make_story EC2-004 "Nginx TLS proxy & SSM-only access" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a security engineer*  
I want vLLM to bind on localhost:8000 and expose **only** port 443
through an Nginx reverse proxy with an ACM certificate,
and I want all admin access via **SSM Session Manager** (no SSH key pairs)
so that the GPU node stays invisible to the public internet
and key management is eliminated.

**Details / Acceptance**

1. Security-group opens 443 from NLB only; 22 closed.  
2. ACM wildcard cert `*.tl-fif.local` imported via CLI.  
3. Nginx config enforces TLS1.2+, HSTS, and gzip off.  
4. `ssm:StartSession` tested from laptop ⇒ shell inside instance.  
5. Documented in `05_docs/02_architecture/ssm_access.md`.
EOF

echo "🎉  Epic 5 and four richly-described stories created"
