
# Refined Epics and User Stories (Optimized for Clarity and Testability)

---

## ### API – Secure Edge API Gateway

**Outcome:**
Authenticated, rate-limited API surface (`/infer`, `/stop`, `/ping`) providing secure, cost-efficient, and audit-compliant API services.

**API-001: API Skeleton & Test Harness**
Context: Set project scaffolding for TDD-driven development and automated tests.
Acceptance Criteria:

* Create package structure: `api/`, empty `routes.py`, pytest scaffold in `tests/`.
* GitHub Action runs `pytest` and intentionally fails on initial placeholder test.
* Include minimal `openapi.yaml` with empty path definitions.
* README details local testing using `uvicorn`.
* Assign ownership via GitHub `CODEOWNERS` file.

**API-002: JWT Authorizer via Cognito**
Context: Validate identity efficiently before requests reach downstream services.
Acceptance Criteria:

* Requests without valid `Authorization` header respond with **401 within 150 ms**.
* Expired/invalid JWTs respond with **403**, forwarding valid claims downstream.
* JWKs cached ≤10 min by API Gateway authorizer.
* Postman tests document happy path and three negative scenarios.
* CI includes contract tests with mocked JWKS.

**API-003: Per-User Throttling & CORS Enforcement**
Context: Mitigate denial-of-service and malicious client traffic.
Acceptance Criteria:

* Limit bursts to **5 req/s**, sustained usage to **20 req/min** per Cognito user.
* Throttled requests return **429** with proper `Retry-After` header.
* Allow CORS only from `http://localhost:*`; reject all other origins.
* Smoke tests verify correct throttling response after exceeding rate.
* Emit metric `RateLimitBreaches` to CloudWatch.

**API-004: Structured JSON Access Logging**
Context: Enable rapid troubleshooting through structured logs.
Acceptance Criteria:

* JSON log entries containing `requestId`, `ip`, `route`, `status`, `latencyMs`.
* Store logs in CloudWatch group `/apigw/tl-fif` with 30-day retention.
* Include predefined Insights query (`queries/api_latency.cwi`).
* CI validation step to assert log fields via AWS SDK stubs.
* CloudWatch alarm triggers at p95 latency ≥300 ms over 5 minutes.

**API-005: Health Check Route (`/ping`)**
Context: Lightweight endpoint for automated uptime checks.
Acceptance Criteria:

* `GET /ping` responds with `{"status":"ok"}` within 100 ms.
* Route is JWT-exempt, restricted to CIDR 10.20.0.0/22.
* Terraform outputs URL usable by external health-checkers (e.g., Pingdom).
* Synthetic CloudWatch canary test runs every minute.
* PagerDuty alert triggered after 3 failures in 5-minute span.

---

## ### LAM – Lambda Router v2

**Outcome:**
Efficient Lambda function (512 MB, Python 3.12) that authenticates, queues jobs, and triggers GPU nodes within stringent latency constraints.

**LAM-001: Lambda Scaffold & Test Infrastructure**
Context: Establish minimal Lambda framework with failing TDD tests.
Acceptance Criteria:

* Initial project structure (`router/handler.py`, pytest-asyncio scaffolding).
* CI pipeline intentionally fails due to placeholder test.
* Makefile target (`make lambda-package`) for packaging Lambda zip files.
* Document local testing approach using SAM CLI.

**LAM-002: JWT & Input Schema Validation**
Context: Validate incoming requests early to prevent downstream cost.
Acceptance Criteria:

* Returns **400** on invalid schema; **401** on missing or invalid JWT.
* Implement JWT verification with `python-jose`.
* Unit tests covering valid, expired, invalid JWT scenarios; prompt size ≤6 kB.
* Enforce test coverage threshold ≥90% for router logic.

**LAM-003: Job Submission to Redis with TTL**
Context: Reliably queue jobs, ensuring automatic job expiration.
Acceptance Criteria:

* Generates UUIDv4; Redis key format: `job:{uuid}`, TTL set to 300 seconds.
* Stored data includes prompt, idle duration, S3 reply destination, timestamp.
* Returns **503** on Redis errors, logs error as `RedisEnqueueFail=1`.
* Integration test verifies Redis TTL accuracy (\~300 s) via `fakeredis`.

**LAM-004: GPU Instance Cold-Start Handling**
Context: Initiate GPU instances conditionally to manage costs.
Acceptance Criteria:

* Checks EC2 instance tagged `env=tinyllama`; initiates `start_instances` if stopped.
* Responds immediately with **202**, JSON: `{"status":"starting","eta":90}`.
* Increment `EC2Starts` CloudWatch metric for each start event.
* Unit tests verify correct cold-start logic using mocked boto3 calls.

**LAM-005: Immediate Queued Response**
Context: Ensure GUI responsiveness by avoiding synchronous wait on inference.
Acceptance Criteria:

* Warm execution latency ≤60 ms (validated with AWS X-Ray).
* JSON response: `{"status":"queued","id":"<uuid>"}`, header `X-Request-Id`.
* CI validates JSON schema and header correctness.
* Enable production canary logging for payload samples (24h rolling log).

---

## ### RED – Redis Job Queue

**Outcome:**
Robust, cost-effective Redis queue ensuring no data leakage or unintended cost escalation.

**RED-001: Redis Infrastructure & Test Framework**
Context: Provision base Terraform infrastructure and validate with failing test.
Acceptance Criteria:

* Create stub Terraform module (`infra/redis/main.tf`), failing terratest script.
* GitHub Actions runs `terratest` with fail-fast enabled.
* Document local Terraform workflow with `aws-vault`.

**RED-002: Secure Redis Cluster Deployment**
Context: Provide secure, high-performance Redis node.
Acceptance Criteria:

* Deploy single-node `t4g.small` instance in private subnet (10.20.1.0/24).
* Restrict SG ingress to Lambda and EC2 security group IDs.
* Enable at-rest encryption; in-transit encryption disabled (within VPC).
* Validate deployment via terratest confirming port security configuration.

**RED-003: Redis Job Schema & TTL Enforcement**
Context: Guarantee predictable memory usage under peak load.
Acceptance Criteria:

* Enforce key pattern (`job:{uuid}`) using Redis Lua script rejection for invalid keys.
* Integration test ensures TTL set accurately (295–305 seconds range).
* Memory usage triggers CloudWatch alarm at ≥70% utilization.
* Document Redis CLI examples for operational troubleshooting.

**RED-004: Queue Health Check Endpoint**
Context: Provide health status endpoint to simplify operational monitoring.
Acceptance Criteria:

* Lambda function (`queue_health.py`) returns latency metrics (`{"redis":"ok","latencyMs":<value>}`).
* Responds with error if latency exceeds 200 ms or Redis is unreachable.
* API Gateway route `/queue-health` JWT-exempt, internal network access only.
* Alarm triggered upon two consecutive 5-minute failures.

---

## ### EC2 – GPU Inference Node Management

**Outcome:**
Efficient GPU node (g4dn.xlarge) providing timely inference with automated resource management.

**EC2-001: GPU AMI Pipeline Scaffold & Test Setup**
Context: Create foundational Image Builder pipeline and initial test harness.
Acceptance Criteria:

* Image Builder directory (`imagebuilder/`), stubbed recipe JSON.
* CI (packer build) deliberately fails initially, awaiting dependencies.
* Unit test with AWS STS mock validating SSM parameter update logic.

**EC2-002: GPU AMI Image Baking**
Context: Ensure minimal boot latency via pre-installed software components.
Acceptance Criteria:

* Bake AMI with CUDA 12, Python 3.10, vLLM 0.4.2, TinyLlama weights.
* Tag AMI with `tl-fif:gpu-node` and build timestamp.
* Ensure Image Builder pipeline duration ≤12 minutes (on `m7g.large`).
* Confirm AMI ID published to SSM parameter `/tl-fif/latest_ami_id`.

**EC2-003: Job Watcher & S3 Response Upload**
Context: Automate job consumption from Redis and response handling via S3.
Acceptance Criteria:

* `watcher.py` retrieves jobs, streams inference results, and uploads to S3.
* Supervisord ensures continuous watcher service, includes Redis back-off logic.
* Integration test confirms functionality via fakeredis and MinIO mock.
* Operational logs include job UUID, latency metrics.

**EC2-004: Automatic Idle Instance Shutdown**
Context: Avoid unnecessary GPU billing by auto-terminating idle instances.
Acceptance Criteria:

* Idle timer reset upon job completion; terminates EC2 instance when timer expires.
* Idle duration configurable via job payload (default: 5 min, range: 1–30 min).
* Logs shutdown activity to CloudWatch (`AutoStops` metric).
* Achieve timer precision within ±5 seconds at p99 confidence.

**EC2-005: TLS Endpoint & Secure Access Management**
Context: Secure GPU endpoint from unauthorized access.
Acceptance Criteria:

* Nginx reverse proxy terminates TLS ≥1.2 (port 443) with ACM-managed certificates.
* vLLM restricted to localhost (`127.0.0.1:8000`); no public inference endpoints.
* EC2 security group permits inbound traffic only from NLB on port 443; SSH closed.
* Document secure access via AWS SSM Session Manager.

---

## ### OPS – Cost & Observability Controls

**Outcome:**
Robust cost-control mechanisms and comprehensive observability to ensure monthly spending ≤€20.

**OPS-001: Observability Infrastructure Setup**
Context: Scaffold infrastructure for observability dashboard and budgeting.
Acceptance Criteria:

* Stub CloudWatch dashboard JSON and initial `cfn-lint` failing test.
* Establish Terraform module stub for budget alarms.
* Ensure CI validation of dashboard JSON compliance.

---

### Sanity Check:

All six Epics (API, LAM, RED, EC2, OPS, CI) clearly defined, non-overlapping, each with distinct, verifiable acceptance criteria, ready for GitHub Issues deployment.
