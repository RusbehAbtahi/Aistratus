### API – Secure Edge API Gateway

Outcome: Expose a single, authenticated HTTP surface (`/infer`, `/stop`, `/ping`) that blocks bad traffic early, enforces cost-safe throttling, and produces audit-grade logs.

**API-001  API Skeleton & Test Harness**
Context: Set up repo folders, pytest infra, and a failing integration test to enforce TDD.
Acceptance Criteria

* Create `api/` package with empty `routes.py`, `tests/` with pytest scaffold
* GitHub Action runs `pytest` and fails on placeholder test
* `openapi.yaml` committed with empty paths section
* README documents local `uvicorn` mock run
* Code owners file routes API PRs to back-end team

**API-002  JWT Authorizer via Cognito**
Context: All edge calls must prove identity without warming downstream services.
Acceptance Criteria

* Requests lacking `Authorization` header return **401 < 150 ms**
* Expired or invalid JWTs return **403**; valid tokens forward claims
* API Gateway caches JWKs ≤ 10 min
* Postman collection shows happy path + three failure cases
* Contract test in CI hits a mocked JWKS endpoint

**API-003  Per-User Throttling & CORS Rules**
Context: Prevent runaway GUI loops and hostile scripts.
Acceptance Criteria

* Burst limit **5 req/s**, sustained **20 req/min** per Cognito `sub`
* Exceeding limits returns **429** with `Retry-After` header
* CORS allows `http://localhost:*`; all other origins blocked
* Smoke test sends 6 rapid calls and asserts last returns 429
* Metrics `RateLimitBreaches` emitted to CloudWatch

**API-004  Structured JSON Access Logs**
Context: Fast incident triage needs machine-parseable logs.
Acceptance Criteria

* Custom log format: `requestId,ip,route,status,latencyMs` JSON object
* Logs land in group `/apigw/tl-fif` with 30-day retention
* CloudWatch Insights query saved as `queries/api_latency.cwi`
* CI asserts log fields via AWS SDK stub
* p95 latency alarm (≥300 ms 5 min) created and enabled

**API-005  /ping Health Route**
Context: Uptime monitors must verify the stack without burning GPU cost.
Acceptance Criteria

* `GET /ping` returns `{"status":"ok"}` in < 100 ms
* Route bypasses JWT but requires VPC-only source CIDR 10.20.0.0/22
* Terraform output supplies synthetic Pingdom URL
* Synthetic test in CloudWatch Synthetics checks every 1 min
* Failure 3/5 iterations triggers PagerDuty alert

---

### LAM – Lambda Router v2

Outcome: Stateless 512 MB Python 3.12 Lambda that authenticates, enqueues, cold-boots GPU, and replies in under 60 ms warm.

**LAM-001  Router Skeleton & Pytest Harness**
Context: Lay project structure and failing test to drive TDD.
Acceptance Criteria

* Create `router/handler.py`, `tests/` with pytest-asyncio scaffold
* CI fails on placeholder test until next story passes
* Add Makefile target `make lambda-package` producing zip
* Document local SAM invoke for developers

**LAM-002  Validate JWT + JSON Schema Guardrail**
Context: Reject bad input before Redis or EC2 cost is incurred.
Acceptance Criteria

* Invalid schema returns **400**; missing/invalid JWT returns **401**
* Uses `python-jose` for signature verification
* Unit tests cover valid, expired, tampered token, and 6 kB prompt cap
* Coverage ≥ 90 % on `router` package

**LAM-003  Redis Enqueue with 5-Min TTL**
Context: Queue must self-clean to avoid memory leaks.
Acceptance Criteria

* Generates UUID v4; writes job key `job:{uuid}` with TTL 300 s
* Value includes prompt, idle minutes, S3 reply path, timestamp
* On Redis error Lambda returns **503** and logs `RedisEnqueueFail=1`
* Integration test uses `fakeredis` to assert TTL ≈ 300 s

**LAM-004  GPU Cold-Boot Logic**
Context: Router decides when to pay for GPU.
Acceptance Criteria

* If EC2 tagged `env=tinyllama` is *stopped*, call `start_instances`
* Return body `{"status":"starting","eta":90}` with 202 status
* Metric `EC2Starts` +1 per cold boot
* Unit test mocks boto3 and asserts decision branch

**LAM-005  Immediate 202 + Request-ID Reply**
Context: GUI must not block UI thread waiting for inference.
Acceptance Criteria

* Warm path latency p95 **≤ 60 ms** (CI step with AWS X-Ray)
* Response `{"status":"queued","id":"<uuid>"}`; header `X-Request-Id` set
* Contract test checks JSON schema and header match
* Canary Lambda in prod logs sample payloads for 24 h

---

### RED – Redis Job Queue

Outcome: A private, low-latency ElastiCache Redis buffering layer that never leaks data or money.

**RED-001  Queue Skeleton & Terraform Harness**
Context: Establish Terraform module layout and failing terratest.
Acceptance Criteria

* `infra/redis/main.tf` stub + `tests/redis_test.go` terratest failing
* GitHub Action runs terratest in `--failfast` mode
* README explains local `aws-vault` usage for plan/apply

**RED-002  Private t4g.small Cluster Provisioning**
Context: Provide minimal cost, sub-millisecond latency queue.
Acceptance Criteria

* Single-node `t4g.small`, subnet 10.20.1.0/24, cluster-mode off
* SG only allows 6379 from Lambda + EC2 SG IDs
* At-rest encryption enabled; in-transit disabled (same VPC)
* Terraform apply passes; terratest asserts port closed to 0.0.0.0/0

**RED-003  Job Schema & 300-Second TTL Policy**
Context: Ensure memory is self-governing under burst load.
Acceptance Criteria

* Key pattern enforced via Lua: non-matching keys rejected
* TTL verified by integration test (`TTL` between 295-305 s)
* Memory alarm triggers at 70 % of node RAM
* Docs include redis-cli example insert/read/delete

**RED-004  /queue-health Diagnostics Route**
Context: Operators need a cheap health probe.
Acceptance Criteria

* New Lambda `queue_health.py` responds `{"redis":"ok","latencyMs":<x>}`
* Fails if ping latency > 200 ms or connection error
* API Gateway internal route `/queue-health` (no JWT) configured
* CloudWatch alarm on 2 × 5 min failures

---

### EC2 – On-Demand GPU Inference Node

Outcome: A hibernated `g4dn.xlarge` AMI that wakes, serves vLLM, and self-stops—first token delivered ≤ 90 s overall.

**EC2-001  AMI Pipeline Skeleton & Test Harness**
Context: Create Image Builder recipe and failing packer test.
Acceptance Criteria

* `imagebuilder/` directory with recipe JSON stub
* Packer CI job builds AMI and expects failure until weights story lands
* Unit test uses `aws sts` mock to assert SSM param update

**EC2-002  Bake AMI with vLLM + Weights**
Context: Skip package install at every cold boot.
Acceptance Criteria

* Image Builder installs CUDA 12, Python 3.10, vLLM 0.4.2, weights gguf
* AMI tagged `tl-fif:gpu-node` + version timestamp
* Build time ≤ 12 min on m7g.large builder
* Publish AMI ID to `/tl-fif/latest_ami_id` SSM param

**EC2-003  watcher.py Consumer + S3 Upload**
Context: Decouple GUI from GPU via S3 replies.
Acceptance Criteria

* `watcher.py` pops Redis job, streams vLLM, uploads JSON to S3
* Supervisord ensures restart; back-off on Redis failure
* Integration test with fakeredis + local MinIO passes
* Logs include job UUID and latency ms

**EC2-004  Idle Self-Stop & Cost Guard**
Context: Kill forgotten GPU sessions automatically.
Acceptance Criteria

* Thread resets timer on every successful inference
* At zero → signed `StopInstances` self-call
* Default 5 min; payload overrides 1-30 min
* CloudWatch metric `AutoStops` increments; p99 accuracy ±5 s

**EC2-005  TLS Proxy & SSM-Only Access**
Context: No public SSH or plaintext inference ports allowed.
Acceptance Criteria

* Nginx reverse proxy terminates TLS 1.2+ on 443 with ACM cert
* vLLM binds 127.0.0.1:8000 only
* SG exposes 443 from NLB; port 22 closed
* SSM Session Manager access demo script documented

---

### OPS – Cost & Observability Guardrails

Outcome: Keep monthly spend ≤ €20 and provide a single dashboard correlating cost, latency, and GPU utilisation.

**OPS-001  Observability Skeleton & Test Harness**
Context: Create CloudWatch dashboard JSON + failing ʻcfn-nagʼ test.
Acceptance Criteria

* `observability/dashboard.json` stub committed
* `cfn-lint` CI job fails on missing widgets
* Budget alarms terraform module stub added

**OPS-002  Publish CurrentSpendEUR Metric**
Context: GUI polls live cost to inform users.
Acceptance Criteria

* EventBridge rule every 15 min triggers `cost_publisher.py` Lambda
* Lambda calls Cost Explorer, emits `TLFIF/Cost/CurrentSpendEUR`
* p99 Lambda duration < 1 s; timeout 3 s
* Unit test stubs Cost Explorer and asserts metric payload

**OPS-003  Budget Alarms €15 Warn / €20 Hard-Stop**
Context: Prevent bill shock.
Acceptance Criteria

* AWS Budgets alarm 75 % → SNS email; 100 % → Lambda `budget_killer.py`
* Killer Lambda stops GPU by tag and logs `BudgetStops` metric
* Terraform plan shows no extra IAM beyond least privilege
* Manual test with budget threshold €0.01 proves shutdown

**OPS-004  Unified CloudWatch Dashboard**
Context: One pane of glass for ops and finance.
Acceptance Criteria

* Widgets: GPU util%, VRAM%, queue depth, p95 latency, CurrentSpendEUR
* JSON imported passes `cfn-lint`; screenshot attached to issue
* Dashboard link added to README; p95 load time < 2 s
* Alarm thresholds visually annotated

---

### CI – Continuous Delivery Pipeline

Outcome: Push-to-merge triggers tests, AMI bake, Lambda deploy, and smoke test—all reproducible and rollback-safe.

**CI-001  Pipeline Skeleton & Failing Smoke Test**
Context: Set guardrails before any code lands.
Acceptance Criteria

* CodePipeline with Source (GitHub) and Test stage only
* Smoke test fails because no code yet; CI status = red
* README badge wired to `main` branch pipeline

**CI-002  Unit Tests ≥ 90 % Coverage Stage**
Context: Block merges with weak tests.
Acceptance Criteria

* CodeBuild container runs `pytest --cov=.`; fails below 90 %
* Coverage HTML artifact uploaded to S3 `coverage/` prefix
* Pipeline time ≤ 5 min on `arm1.medium` build image

**CI-003  AMI Bake Stage Integration**
Context: Ensure infrastructure immutability.
Acceptance Criteria

* Pipeline calls Image Builder execution; waits for success callback
* On success, updates SSM `/tl-fif/latest_ami_id`
* Build cost per run ≤ €0.03 (assert via Cost Explorer check)
* Failing bake blocks downstream stages

**CI-004  Lambda Router Auto-Deploy + Rollback**
Context: Ship routing fixes safely.
Acceptance Criteria

* Post-unit stage zips router, publishes new version, shifts `prod` alias
* Previous five versions retained; rollback script documented
* Slack webhook posts deploy summary with X-Ray trace link
* Integration test hits `/ping` and expects status ok

**CI-005  End-to-End Smoke Test**
Context: Guarantee the whole path works after every deploy.
Acceptance Criteria

* Pipeline step invokes GUI headless script: prompt→S3 reply in ≤ 120 s
* Fails fast on 3 successive 5xx responses
* Test artifacts (JSON reply, logs) stored in S3 for 7 days
* Pipeline marks build unstable, not failed, when latency > 90 s but < 120 s

---

### Sanity-Check

All six Epics (API, LAM, RED, EC2, OPS, CI) are covered with distinct, non-overlapping stories; every critical behaviour has at least one testable ticket.
