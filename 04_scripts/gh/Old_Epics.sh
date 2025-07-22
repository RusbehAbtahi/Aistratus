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

Stand up a secure, well-documented HTTP API layer that exposes three routes—`/infer`, `/stop`, and `/health`—behind Amazon API Gateway (HTTP API).  
All requests must carry a valid JWT issued by Cognito; throttling protects back-end resources; structured access-logs land in CloudWatch.

**Why this matters**

The API is the *contract* between every current and future client (desktop, CLI, mobile app) and the cloud back-end.  
A rock-solid API surface gives front-end developers a stable target, lets DevOps set cost-control guardrails early, and surfaces abuse patterns in logs before they hurt our budget.

**Success / Acceptance**

1. A developer can run `curl -H "Authorization: Bearer <valid>" https://…/health` and get `{"status":"ok"}`.  
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
I need a published OpenAPI 3 spec that declares `/infer`, `/stop`, and `/health`
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
#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_cicd.sh — Epic 7 (CI/CD & AMI pipeline) + 4 rich stories
#
# Prereqs : gh auth login ✔ • milestone exists
# Usage   : bash 04_scripts/gh/create_epic_cicd.sh
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create cicd  --description "CI/CD pipeline work"                --color 27AE60 2>/dev/null || true
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story --description "Individual user story"              --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_cicd.md <<'EOF'
**Epic Goal**

Create a **single-click CI/CD pipeline** that:

1. Builds and unit-tests code on every push to *main*.  
2. Bakes a new GPU AMI via EC2 Image Builder on successful tests.  
3. Requires human approval for AMI promotion.  
4. Deploys updated Lambda Router automatically.  
5. Publishes artefacts and pipeline status badges back to GitHub.

**Why this matters**

Manual deployments are error-prone and slow.  
A codified pipeline:

* Makes every infra change reviewable and reproducible.  
* Provides instant feedback on unit-test regressions.  
* Gives us a rollback “easy button” (re-point LaunchTemplate to previous AMI).  

Without a robust pipeline, we risk snowballing drift between docs, code, and production.

**Success / Acceptance**

* Pushing a commit to *main* triggers CodePipeline ➔ green end-to-end run.  
* A failed unit test halts the pipeline; no AMI or Lambda deploy occurs.  
* Previous AMI versions (last 5) remain available for rollback.  
* Pipeline cost ≤ €0.03 per run (graviton CodeBuild, short Image Builder step).
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 7 – CI/CD & AMI pipeline" \
  --label epic,cicd \
  --body-file /tmp/epic_cicd.md \
  --milestone "$MILESTONE" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "✅  Epic #$EPIC_ID created"

# ---------- 2. Helper --------------------------------------------------------
make_story () {
  local code="$1"; shift
  local title="$1"; shift
  local tmp; tmp=$(mktemp)
  cat > "$tmp"
  gh issue create --title "${code}  ${title}" \
    --label cicd,story --milestone "$MILESTONE" \
    --body-file "$tmp" >/dev/null
  rm "$tmp"
  echo "   • ${code} created"
}

# ---------- 3. Stories -------------------------------------------------------
make_story CI-001 "Pipeline triggers on every push to main" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a developer*  
I want CodePipeline to start automatically whenever a commit lands on the *main* branch,  
so that every change—code or documentation—passes tests before merging into production.

**Details / Acceptance**

1. CodeStar Connections links GitHub repo to AWS.  
2. Source stage watches `refs/heads/main`.  
3. Webhook trigger verified by pushing a dummy commit; pipeline initiates within 30 s.  
4. README badge shows latest pipeline status (`passing` / `failing`).
EOF

make_story CI-002 "CodeBuild stage runs unit tests ≥ 90 % coverage" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a quality advocate*  
I want CodeBuild to run `pytest` with coverage enforced at **90 %**  
so that regressions are caught before deployment.

**Details / Acceptance**

1. `buildspec.yml` installs deps, runs `pytest --cov=.`.  
2. Coverage threshold enforced via `coverage xml && coverage html`.  
3. Failing tests ➔ pipeline stops; GitHub commit status set to `failure`.  
4. Artifacts: `coverage.html` uploaded to S3 for inspection.
EOF

make_story CI-003 "Image Builder stage bakes GPU AMI" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a release engineer*  
I want a dedicated Image Builder stage that creates a versioned AMI  
so every deployment is traceable and repeatable.

**Details / Acceptance**

1. CodeBuild calls `aws imagebuilder start-image-pipeline-execution`.  
2. On success, SSM Param `/tl-fif/latest_ami_id` updated automatically.  
3. Image recipe & pipeline defined in `infra/imagebuilder/` IaC folder.  
4. Average bake time ≤ 12 min on m7g.large builder instance.
EOF

make_story CI-004 "Auto-deploy Lambda Router + easy rollback" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As an operator*  
I need the pipeline to publish a new Lambda version, shift the `prod` alias,  
and provide a one-click rollback to the previous version  
so I can recover instantly from bad deploys.

**Details / Acceptance**

1. Post-build: `zip` Lambda → `aws lambda publish-version`.  
2. `aws lambda update-alias --function-name lambda_router --name prod --function-version <new>`  
3. Previous 5 versions retained; rollback doc in README.  
4. Success notification posted to Slack/#deploys (SNS).
EOF

echo "🎉  Epic 7 and four richly-described stories created"
#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_costops.sh — Epic 6 (Cost & Monitoring) + 4 rich stories
#
# Prereqs : gh auth login ✔ • labels & milestone exist or are created here
# Usage   : bash 04_scripts/gh/create_epic_costops.sh
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create ops   --description "Cost & monitoring work"              --color 95A5A6 2>/dev/null || true
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story --description "Individual user story"               --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_ops.md <<'EOF'
**Epic Goal**

Implement a lightweight **observability and cost-guardrail layer** that:

* Publishes a live spend metric the GUI can poll (`CurrentSpendEUR`).  
* Shows GPU utilisation, latency, and queue depth on a single CloudWatch dashboard.  
* Fires budget alarms at €15 (warning) and €20 (hard stop → auto-shutdown).  
* Provides a manual, GUI-exposed emergency “Stop GPU” that always works.

**Why this matters**

TinyLlama’s competitive edge is *running cheaply*.  
Every hour of forgotten GPU time destroys that promise.  
Early, automated cost-signals keep the PO confident and prevent end-of-month surprises, while dashboards help diagnose latency spikes long before users complain.

**Success / Acceptance**

1. GUI sees spend updates every 30 s via Lambda metric proxy.  
2. When monthly spend hits €15 a Slack/email alert fires; at €20 a Lambda stops EC2.  
3. CloudWatch dashboard shows: GPU util%, VRAM%, p95 latency, queue depth, spend.  
4. All guardrails IaC-defined; no manual console tweaks.
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 6 – Cost governance & monitoring" \
  --label epic,ops \
  --body-file /tmp/epic_ops.md \
  --milestone "$MILESTONE" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "✅  Epic #$EPIC_ID created"

# ---------- 2. Helper --------------------------------------------------------
make_story () {
  local code="$1"; shift
  local title="$1"; shift
  local tmp; tmp=$(mktemp)
  cat > "$tmp"
  gh issue create --title "${code}  ${title}" \
    --label ops,story --milestone "$MILESTONE" \
    --body-file "$tmp" >/dev/null
  rm "$tmp"
  echo "   • ${code} created"
}

# ---------- 3. Stories -------------------------------------------------------
make_story OPS-001 "Publish custom metric CurrentSpendEUR" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a cost-aware user*  
I want the GUI to display live AWS spend in Euros, refreshed every 30 seconds,  
so I instantly see the impact of long sessions or mistakes.

**Details / Acceptance**

1. Lambda `cost_publisher.py` calls Cost Explorer → `put_metric_data` into namespace `TLFIF/Cost`.  
2. Metric name `CurrentSpendEUR`, value rounded to €0.01.  
3. Cron Schedule: EventBridge rule every **15 min** (cost calls are rate-limited).  
4. GUI polls a lightweight `/cost` route that returns the latest datapoint.  
5. README documents how to enable Cost Explorer API for new accounts.
EOF

make_story OPS-002 "Budget alarms €15 warn / €20 auto-stop" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As the budget owner*  
I need AWS Budgets to warn me at €15 and hard-stop the GPU at €20  
so monthly spend can never exceed a pizza night.

**Details / Acceptance**

1. Budget name `TinyLlama-Monthly`. Period: Calendar month. Scope: entire account.  
2. SNS topic `budget-alerts`. Email subscription `rusbeh@…`.  
3. Warning action: SNS email at 75 %.  
4. Hard-stop action: SNS → Lambda `budget_killer.py` → `ec2:StopInstances` on tag `env=tinyllama`.  
5. PR includes Terraform or CloudFormation template + README test steps.
EOF

make_story OPS-003 "Unified CloudWatch dashboard" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As an operator*  
I want a single CloudWatch dashboard showing GPU utilisation, VRAM %, queue depth, p95 latency, and CurrentSpendEUR  
so that I can correlate performance with cost in one glance.

**Details / Acceptance**

1. Dashboard name `TLFIF-Intermediate`.  
2. Widgets: (a) line GPU util %, (b) line VRAM %, (c) single-value p95 latency, (d) bar queue depth, (e) line spend €.  
3. JSON dashboard definition committed to `05_docs/02_architecture/cloudwatch_dashboard.json`.  
4. Screenshot attached to issue on completion.
EOF

make_story OPS-004 "GUI emergency Stop GPU always functional" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a nervous user*  
I need the red “Stop GPU” button to work even if Redis or Lambda are broken,  
so I can guarantee runaway costs end in <10 s.

**Details / Acceptance**

1. GUI button calls dedicated `/stop` route → API Gateway directly hits Lambda with short timeout.  
2. Lambda bypasses Redis and calls `StopInstances` unconditionally.  
3. GUI shows spinner and success/fail toast.  
4. Chaos-test: kill Redis; press Stop GPU → instance stops, metric `ManualStops` +1.
EOF

echo "🎉  Epic 6 and four richly-described stories created"
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
#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_gui.sh — Creates Epic 1 + 6 GUI stories, labels, milestone
# Prereqs: gh auth login  ✔, repo cloned, run from repo root
# Usage:   bash 04_scripts/gh/create_epic_gui.sh
# ------------------------------------------------------------------
set -euo pipefail

# ---------- 0.  Labels ------------------------------------------------
echo "==> Ensuring labels"
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create gui   --description "Desktop GUI work"                      --color 1D76DB 2>/dev/null || true
gh label create story --description "Individual user story"                --color 7057FF 2>/dev/null || true

# ---------- 1.  Milestone ---------------------------------------------
echo "==> Ensuring milestone"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api "repos/$REPO/milestones" \
  -f title="Intermediate Stage" \
  -f state="open" \
  -F description="All intermediate-stage work (GUI + on-demand GPU inference)" \
  > /dev/null 2>&1 || true   # Ignore 'already exists'

# ---------- 2.  Epic ---------------------------------------------------
echo "==> Creating Epic 1 – Desktop GUI core"
cat > /tmp/epic_gui.md <<'EOF'
**Epic Goal**

Deliver a cross-platform Tkinter desktop app so the user can  
• type a prompt, send it, watch live cost, and hard-stop the GPU.

**Why it matters**

GUI is the single human entry-point; even a stub forces clear API contracts.

**Acceptance**

– Stories GUI-001…GUI-006 all *Done*  
– Demo on Win/macOS: prompt → reply → cost tick  
– PO signs off on UX & cost controls
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 1 – Desktop GUI core" \
  --label epic,gui \
  --body-file /tmp/epic_gui.md \
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
    --label gui,story \
    --body-file /tmp/body.md \
    --milestone "Intermediate Stage" \
    > /dev/null
  echo "  • $id created"
}

# ---------- 4.  Six stories --------------------------------------------
echo "==> Creating GUI stories"
create_story "GUI-001" "Prompt box accepts multi-line input" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I can enter multi-line prompts and press **Ctrl+Enter** to send.

**Acceptance**
1. Tkinter Text widget, 5 rows × 80 cols.
2. Ctrl+Enter triggers the same handler as Send.
3. Newlines preserved in JSON payload.
4. Unit test posts mock payload."

create_story "GUI-002" "Send button disables & shows spinner" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I see a spinner while inference runs, preventing duplicates.

**Acceptance**
1. Button disabled & spinner visible on click.
2. Re-enabled on success/error.
3. Unit test simulates 2-s API call."

create_story "GUI-003" "Red Stop-GPU button triggers /stop" \
"Belongs to **Epic #$EPIC_ID**

*As a cost-conscious user* I can stop the GPU within 10 s.

**Acceptance**
1. Red button (#d9534f), label \"Stop GPU\".
2. POST /stop; toast on success; error visible.
3. CloudWatch metric ManualStops increments."

create_story "GUI-004" "Idle-timeout spinbox controls auto-stop" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I set idle-timeout 1-30 min so EC2 self-stops.

**Acceptance**
1. ttk.Spinbox 1-30 min, default 5.
2. Value saved in ~/.tl-fif.ini.
3. Included in /infer JSON.
4. Functional test: 1 min → EC2 stops ~70 s later."

create_story "GUI-005" "Cost label polls live spend" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I see running € cost updated every 30 s.

**Acceptance**
1. Poll metric CurrentSpendEUR.
2. Label shows \"€ <value> (today)\".
3. Orange >€10, red >€15.
4. Unit test mocks metric endpoint."

create_story "GUI-006" "Output pane shows full conversation" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I can scroll all prompts/replies with timestamps.

**Acceptance**
1. Read-only ScrolledText widget.
2. HH:MM:SS timestamps.
3. Scroll position persists.
4. Unit test verifies order & time."

echo "==> GUI epic and six stories DONE"
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
gh issue create \
  --title "GUI-007: Refactor Desktop Codebase into Modular MVC + Services Architecture" \
  --body "$(cat <<'EOF'
This issue tracks the structural refactor of the TinyLlama desktop GUI into a modular, professional architecture, replacing app.py with clean separation of view, controllers, shared state, and services as confirmed in Epic 1.

---

## 1 · Problem / Motivation  
`app.py` has grown into a 160-line “god-class” that mixes Tkinter widgets, HTTP calls, threading, persistence, and cost polling. This makes maintenance difficult, unit-tests brittle, and AI-assisted edits risky. Before adding Cognito auth, EC2 job polling, or mobile clients, the GUI must be split into clear, isolated modules.

## 2 · Goal (Definition of Done)  
Replace the monolith with the **TinyLlama Desktop Modular Architecture** confirmed in Epic 1. All existing GUI features (prompt send, spinner, cost label, idle spinbox, GPU stop, output pane, tests) must still work and all 15 tests must pass unchanged or with minimal rewiring.

## 3 · Reference Architecture (UML diagram will be attached manually)

## 4 · New File / Module Layout  

01_src/tinyllama/gui/
├── gui_view.py          # pure Tkinter view
├── thread_service.py    # background scheduling helper
├── app_state.py         # shared dataclass + tiny event bus
├── controllers/
│   ├── prompt_controller.py
│   ├── gpu_controller.py
│   ├── cost_controller.py
│   └── auth_controller.py
└── main.py              # composition root

*Each file should stay under ~80 LOC with one clear responsibility.*

## 5 · Key Responsibilities  

- **TinyLlamaView**: Defines widgets, layout, and exposes lightweight callback slots. No business logic.
- **AppState**: Dataclass fields (`idle_minutes`, `auth_token`, `current_cost`, `history`). Simple observer/callback list for UI updates.
- **ThreadService**: `run_async(fn, *args)` and `schedule(interval, fn)`, marshals back to UI thread.
- **PromptController**: Builds JSON payload, POSTs `/infer`, updates AppState with reply.
- **GPUController**: POSTs `/stop` (and later `/start`), updates AppState.
- **CostController**: Fetches `/cost` every 30s, pushes to AppState.
- **AuthController**: Launches Cognito login, manages tokens, stores in AppState.
- **main.py**: Wires all components and runs `view.mainloop()`.

## 6 · Testing Strategy  

- GUI (view) tests: Only verify that each button’s command points to the proper controller method.
- Controller tests: Pure Python, mock requests, interact with dummy AppState, verify side-effects.
- Integration smoke test (optional): Run main.py with ThreadService in sync mode, simulate prompt, assert updates.

All existing 15 tests must pass or be replaced with equivalent tests in the new layout.

## 7 · Acceptance Criteria  

1. File split matches layout; no Tk imports in controllers; no `requests` inside view.
2. Functionality parity: GUI behaves exactly like before.
3. Thread safety: all background work runs through ThreadService.
4. Tests green: `TL_TESTING=1 pytest 02_tests/gui` passes on all platforms.
5. Documentation: update README.md and architecture docs.
6. Commit log: single feature branch `feature/GUI-007-refactor-mvc`, squash-merge to main.

## 8 · Out of Scope  

- No new cloud features, Cognito flows, or Redis polling—controllers may stub these.
- No change to user-visible UX or styling.
- No dependency on external frameworks (keep pure Tkinter + stdlib).

## 9 · Implementation Checklist  

1. Scaffold `app_state.py` & `thread_service.py` (unit-test first).
2. Copy widgets from `app.py` into `gui_view.py`; strip logic.
3. Create controllers; port logic; inject dependencies via constructor.
4. Build `main.py` to wire everything.
5. Rewrite/relocate tests; remove old monkey-patch hacks.
6. Delete legacy `app.py` once tests pass.
7. Update docs and push PR.

*Attach UML class diagram after ticket creation.*

EOF
)"
