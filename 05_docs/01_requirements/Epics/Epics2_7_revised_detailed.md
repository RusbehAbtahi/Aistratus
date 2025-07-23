Below are the **full-detail expansions for every ticket in Epic 2 (API — Secure Edge Gateway)**.
Each ticket now has **Context → Acceptance Criteria → Technical Notes/Steps**, at a level suitable for direct conversion into GitHub issues or shell-generated `gh issue create` commands.
I will continue with Epics 3-7 in subsequent messages.

---

## **API-003 · Gateway Hardening & Per-User Throttling**

### Context

The public HTTP API (`/infer`, `/stop`, `/health`) must enforce **Cognito-JWT authentication** and protect against abuse (GUI retry loops, script attacks). Past audits flagged two risks: (1) route settings can be overwritten by stage-level imports, and (2) API Gateway’s default logging obscures the client `sub`, making forensic work tedious.

### Acceptance Criteria

1. **JWT Verification**

   * Requests without `Authorization: Bearer <id token>` → **401** in ≤ 150 ms.
   * Expired or malformed tokens → **403** with body `{"error":"invalid_token"}`.
   * JWKS cached ≤ 10 min; cache-miss latency ≤ 300 ms (cold).

2. **Per-User Throttling**

   * Burst ≤ 5 req/s, rate ≤ 20 req/min **per Cognito `sub`**.
   * Exceeding limits returns **429** and header `Retry-After: 60`.
   * CloudWatch metric `ApiRateLimitBreaches` increments on every 429.

3. **Immutable Route Settings**

   * Terraform resource `aws_apigatewayv2_route_settings` applied to each route with explicit `throttling_burst_limit` and `throttling_rate_limit`.
   * A Terraform **post-apply test** (`tests/api_route_settings_test.py`, using boto3) asserts the burst/rate limits match the Terraform values.

4. **Positive & Negative Tests** (CI job `api_hardening_spec`)

   * Postman/newman collection runs:

     * valid token ✓200,
     * missing token ✓401,
     * tampered signature ✓403,
     * 6 rapid calls ✓1×429.

5. **Documentation**
   `docs/api/jwt_auth.md` explains Cognito pool IDs, import script, and provides `curl` examples for each failure mode.

### Technical Notes / Steps

* **Terraform** (`infra/api/main.tf`)

  ```hcl
  resource "aws_apigatewayv2_route_settings" "infer_rl" {
    api_id                = aws_apigatewayv2_api.edge.id
    stage_name            = aws_apigatewayv2_stage.prod.name
    route_key             = "POST /infer"
    throttling_burst_limit = 5
    throttling_rate_limit  = 20
  }
  # repeat for /stop and /health …
  ```

* **Authorizer** (`modules/auth/cognito.tf`) generates pool + app-client; output the issuer URL and JWKs URI for `openapi.yaml` security schema.

* **Contract Tests**:

  ```bash
  newman run tests/postman/api_hardening.postman_collection.json \
         --env-var ISSUER_URL=$COGNITO_ISSUER \
         --env-var CLIENT_ID=$COGNITO_APP_ID
  ```

* **CI Hook**: GitHub Action `api_hardening.yml` blocks merge unless all Postman tests pass and `pytest tests/api_route_settings_test.py` is green.

* **Cost**: extra CloudWatch metrics ≈ €0.05/mo; JWT authorizer execution ≈ €0.40/mo at 50 req/day.

---

## **API-004 · CORS & Structured JSON Access Logging**

### Context

Frontend (Tkinter GUI and future mobile) is served from `localhost` and potentially file URLs; all other origins must be rejected. Audit RISK-note highlighted that default access logs are unstructured and retention unspecified.

### Acceptance Criteria

1. **CORS Policy**

   * Allowed origins: `http://localhost:*` and `capacitor://*`.
   * Allowed methods: `POST, GET, OPTIONS`; headers: `Authorization, Content-Type`.
   * Pre-flight (`OPTIONS`) returns **204** under 100 ms.

2. **Structured Logging**

   * Enable JSON access logging with fields
     `requestId, ip, route, status, jwtSub, latencyMs, userAgent`.
   * Logs shipped to CloudWatch group `/apigw/tinyllama-access` with `retention_in_days = 30`.

3. **Cost Estimate** comment in Terraform: ≤ 100 MB/mo ≈ €0.00 (free tier); flag alert at 70 MB.

4. **Smoke Test**

   * CI sends `OPTIONS /infer` from disallowed origin → **403**.
   * Logs must contain `origin":"evil.com"` and `status":403`.

### Technical Notes

* Terraform snippet for CORS on HTTP API Stage:

  ```hcl
  cors_configuration {
    allow_origins = ["http://localhost:*", "capacitor://*"]
    allow_methods = ["GET","POST","OPTIONS"]
    allow_headers = ["Authorization","Content-Type"]
  }
  ```

* Access-log format:

  ```json
  $context.requestId $context.identity.sourceIp ...
  ```

  (full `access_log_settings` JSON in `infra/api/logging.tf`).

* Add CloudWatch Insights query (`queries/api_5xx.cwi`) committed under `observability/`.

---

## **API-005 · GUI Login Button → Cognito OAuth Flow**

### Context

The Tkinter GUI now has a **“Login”** button (see `gui_view.py`). Pressing it must open the Cognito Hosted-UI, complete the OAuth code flow, and store the ID token in memory; no AWS keys are ever written to disk.

### Acceptance Criteria

1. **Desktop Flow**

   * Button click opens system browser at `{COGNITO_DOMAIN}/oauth2/authorize?...` with `redirect_uri=http://127.0.0.1:8765/callback`.
   * Local HTTP server (embedded in `auth_controller.py`) listens once, captures `code`, exchanges for tokens via `grant_type=authorization_code`.
   * On success, AppState.auth\_status → `ok`; lamp turns green within 3 s.

2. **Token Handling**

   * Store `id_token` in memory only; **no refresh token** stored.
   * Automatically refresh by re-login when a 401 appears.

3. **Security**

   * `PKCE` (S256) required.
   * Loopback redirect uses random, non-privileged port; listener shuts down after 30 s.

4. **Tests**

   * `tests/gui/test_auth_controller.py` mocks Cognito endpoints and asserts state lamp transitions (`off→pending→ok`).
   * Integration test on CI uses headless Chrome + local Cognito stub.

5. **Docs**

   * `docs/gui/login_flow.md` includes sequence diagram and troubleshooting tips (e.g., Keychain pop-ups on macOS).

### Technical Notes

* **env vars** in GUI: `COGNITO_DOMAIN`, `COGNITO_CLIENT_ID`.

* **Python code** (excerpt)

  ```python
  code_verifier = secrets.token_urlsafe(64)
  code_challenge = base64.urlsafe_b64encode(
      hashlib.sha256(code_verifier.encode()).digest()
  ).rstrip(b"=").decode()
  auth_url = (
      f"{os.environ['COGNITO_DOMAIN']}/oauth2/authorize"
      f"?client_id={os.environ['COGNITO_CLIENT_ID']}"
      f"&response_type=code"
      f"&scope=openid"
      f"&redirect_uri={redirect}"
      f"&code_challenge={code_challenge}"
      f"&code_challenge_method=S256"
  )
  webbrowser.open(auth_url)
  ```

* **Idle logout**: when AppState detects no user activity for 60 min, clear token.

Below is the full-detail expansion for **Epic 3 – LAM (Lambda Router v2)**.
Three tickets (LAM-001 … 003) are now fleshed out to the same depth as the API tickets; each is immediately actionable for scripted GitHub issue creation.

---

## **LAM-001 · Enable Router & Real JWT / Body Validation**

### Context

`tinyllama-router` is currently disabled in prod via `TL_DISABLE_LAM_ROUTER="1"`. We must flip that flag, hard-wire JWT verification identical to API-003, and validate the JSON body (`prompt`, `idle`) before spending Redis/EC2 cost. Prior audits flagged missing rollback steps and unclear CI packaging.

### Acceptance Criteria

1. **Activation**

   * Terraform sets `environment { variables = { TL_DISABLE_LAM_ROUTER = "0" } }`.
   * `terraform apply` publishes new version, shifts alias **prod**; previous 5 versions retained.

2. **JWT Verification**

   * Uses shared lib `tinyllama.utils.auth.verify_jwt(token, issuer, aud)` (import path matches `jwt_tools.py`).
   * Invalid JWT → **401**, body `{"error":"invalid_token"}`; latency ≤ 100 ms (cold ≤ 350 ms).

3. **Schema Validation**

   * Request JSON must match:

     ```json
     { "prompt": "<string 1-6 kB>", "idle": <int 1-30> }
     ```
   * Exceeding limits → **400** with field-specific error.
   * Validation performed via `pydantic` model; code coverage ≥ 95 % on model/handler.

4. **Rollback**

   * `make lambda-rollback VERSION=$PREV` script documented; RUNBOOK section added to `docs/ops/lambda_router.md`.
   * GitHub Action `router_canary.yml` hits `/health` every 5 min; two failures trigger auto-rollback via `aws lambda update-alias --function-name tinyllama-router --name prod --function-version $PREV`.

5. **Tests** (CI job `lam_router_spec`)

   * Unit tests: happy path, >6 kB prompt, idle=0, tampered JWT.
   * Contract test runs `sam local invoke` with Docker to ensure env var wired.
   * p95 duration in X-Ray segment must be < 60 ms warm.

### Technical Notes / Steps

* **Terraform** (`infra/lambda/router.tf`)

  ```hcl
  resource "aws_lambda_function" "router" {
    filename         = data.archive_file.router_zip.output_path
    handler          = "tinyllama.router.handler.lambda_handler"
    runtime          = "python3.12"
    memory_size      = 512
    timeout          = 30
    environment {
      variables = {
        TL_DISABLE_LAM_ROUTER = "0"
        COGNITO_ISSUER        = var.cognito_issuer
        COGNITO_AUD           = var.COGNITO_CLIENT_ID
      }
    }
    layers = [aws_lambda_layer_version.shared_deps.arn]
    tracing_config { mode = "Active" }
  }
  ```

* **Python skeleton** (`01_src/tinyllama/router/handler.py`)

  ```python
  from tinyllama.utils.auth import verify_jwt
  from tinyllama.utils.schema import PromptReq

  def lambda_handler(evt, ctx):
      hdr = evt["headers"].get("authorization","")
      token = hdr.removeprefix("Bearer ")
      verify_jwt(token, os.environ["COGNITO_ISSUER"],
                 os.environ["COGNITO_AUD"])
      body = PromptReq.model_validate_json(evt["body"])
      # enqueue logic in next ticket …
      return {"statusCode":202,"body":'{"status":"queued"}'}
  ```

* **Cost impact**: +€0.10/mo (extra Lambda invocations, X-Ray traces).

---

## **LAM-002 · Redis Enqueue with 5-Minute TTL**

### Context

Router must place validated jobs into Redis (`RED-001`) using a strict schema and auto-expire orphaned entries after 300 seconds. Prior audit demanded error fallback and SG verification.

### Acceptance Criteria

1. **Enqueue Logic**

   * Key pattern: `job:{uuid}`.
   * Value JSON contains `prompt`, `idle`, `reply_s3`, `ts`.
   * `EX 300` set atomically (`SET key val EX 300 NX`).

2. **Happy Path**

   * Returns **202** `{"status":"queued","id":"<uuid>"}` ≤ 60 ms warm.

3. **Failure Handling**

   * Redis timeout or auth failure → **503** `{"error":"queue_unavailable"}`; CloudWatch metric `RedisEnqueueFail`+1.
   * No retry inside Lambda (caller decides).

4. **Security**

   * Lambda SG allows egress to Redis SG 6379 only; verified in terratest (`tests/sg_ingress_test.go`).

5. **Tests**

   * Unit test with `fakeredis` asserts TTL between 295–305 s.
   * Integration test in CI uses real ElastiCache endpoint in dev account (tag-scoped IAM).

### Technical Notes

* **Python** enqueue snippet (add to handler):

  ```python
  import redis, uuid, json, os, boto3, time
  r = redis.Redis(host=os.environ["REDIS_HOST"], port=6379,
                  socket_timeout=0.05)
  jid = str(uuid.uuid4())
  job = {"prompt": body.prompt,
         "idle": body.idle,
         "reply_s3": f"s3://{os.environ['REPLY_BUCKET']}/{jid}.json",
         "ts": int(time.time()*1000)}
  if not r.set(f"job:{jid}", json.dumps(job), ex=300, nx=True):
      raise RuntimeError("Job collision")
  return {"statusCode":202,"body":json.dumps({"status":"queued","id":jid})}
  ```

* **Alarm**: CloudWatch alarm `RedisEnqueueFail >=3 in 5m` → SNS `#tinyllama-alerts`.

* **Cost**: Redis additional commands negligible; CloudWatch metrics ≈ €0.02/mo.

---

## **LAM-003 · GPU Cold-Boot Logic**

### Context

If the GPU EC2 instance (`EC2-001`) is **stopped**, Router must start it and immediately inform GUI of a \~90 s ETA. Audit noted missing metric and unclear client-poll strategy.

### Acceptance Criteria

1. **Start Decision**

   * Router queries EC2 by tag `Project=tinyllama` && `Role=gpu-node`.
   * If state `stopped|stopping|terminated` → call `start_instances`.
   * If state `pending|running` → skip start.

2. **Immediate Response**

   * When a cold start is triggered, Router returns **202**
     `{"status":"starting","eta":90}` and header `X-GPU-ColdBoot:true`.
   * GUI must poll `/health` until 200.

3. **Metrics**

   * `EC2Starts` (Dim\:Reason=ColdBoot) `PutMetricData` on every start.
   * p95 start\_instances API latency ≤ 400 ms.

4. **Idempotency**

   * Second request during `pending` state must *not* call start again; still returns `starting`.

5. **Tests**

   * Unit test with `botocore.stub.Stubber` asserts tag filter & idempotency.
   * CI integration test starts a t3.micro in dev to avoid GPU billing; checks metric emission.

6. **Rollback Safety**

   * If Lambda fails to start instances (limit, insufficient capacity), returns **503** with error details; GUI shows toast.

### Technical Notes

* **Python** excerpt:

  ```python
  ec2 = boto3.client("ec2")
  res = ec2.describe_instances(Filters=[
      {"Name":"tag:Project","Values":["tinyllama"]},
      {"Name":"tag:Role","Values":["gpu-node"]}
  ])
  iid = res["Reservations"][0]["Instances"][0]["InstanceId"]
  state = res["Reservations"][0]["Instances"][0]["State"]["Name"]
  if state == "stopped":
      ec2.start_instances(InstanceIds=[iid])
      cw.put_metric_data(
          Namespace="TLFIF",
          MetricData=[{"MetricName":"EC2Starts","Value":1,
                       "Unit":"Count","Dimensions":[
                           {"Name":"Reason","Value":"ColdBoot"}]}])
      return _starting_response()
  elif state in ("pending","running"):
      return _starting_response() if state=="pending" else _normal_flow()
  else:
      return _error("instance_unavailable")
  ```

* **Cost**: start API free; GPU uptime cost accounted in EC2 epic.

---
Below are the full-detail expansions for **Epic 4 – RED (Redis Job Queue)**, matching the depth of the previous tickets.
Next response will cover Epic 5 (EC2).

---

## **RED-001 · t4g.small Redis Queue (Private, Auto-Destroy When Idle)**

### Context

A lightweight Redis 6.2 cluster buffers inference jobs between Lambda Router and the GPU node. Cost discipline is critical: the node must exist **only** when `var.use_gpu = true`. Prior audit flagged two pain points: daily `-target` destroy plans (anti-pattern) and overly permissive egress. This ticket replaces the destroy-plan with **conditional creation** (`count`) and enforces least-privilege SG rules while ensuring Terraform state consistency.

### Acceptance Criteria

1. **Conditional Provisioning**

   * Terraform module parameter `enable_redis` (default **false**).
   * Cluster resources (`aws_elasticache_cluster`, subnet-group, SG) use `count = var.enable_redis ? 1 : 0`.
   * `terraform plan -var='enable_redis=false'` shows *no* Redis diff; flipping to `true` creates cluster in ≥ 3 min.

2. **Cluster Specification**

   * Single-node `t4g.small`, engine `redis 6.2`.
   * Subnet group `tl-fif-priv` (10.20.1.0/24).
   * `transit_encryption_enabled = false` (inside VPC), `at_rest_encryption_enabled = true`.
   * Parameter group sets `maxmemory-policy = allkeys-lru`.

3. **Security Groups**

   * Ingress: port 6379 **only** from Lambda SG and EC2 SG (`aws_security_group.lambda.id`, `aws_security_group.gpu.id`).
   * Egress: **deny all** except `prefix_list_ids = [aws_ec2_managed_prefix_list.aws_services.id]` to reach NAT for telemetry.
   * `terraform apply` followed by `nmap -p 6379 <redis-endpoint>` from a public host must show **closed**.

4. **Lifecycle & Cost Guardrails**

   * Idle-destroy logic replaced by `enable_redis` flag toggle in CI job `toggle_redis.yml`.
   * CI runs nightly; if GPU is **stopped for ≥12 h**, it auto-commits `enable_redis=false` and applies.
   * Comment in CI logs shows estimated monthly savings.

5. **Monitoring & Alarms**

   * CloudWatch alarm `RedisMemory70` triggers at 70 % used-memory; SNS `#tinyllama-alerts`.
   * Metric `TLFIF/Queue/Enqueues` emitted by Lambda Router for each job.

6. **Tests**

   * **Terratest** (`tests/redis_test.go`) asserts:

     * Cluster created when flag true; absent when false.
     * Security group ingress includes only allowed SG IDs.
   * **Integration**: Python script `ci/redis_smoke.py` connects, sets a key with `EX 10`, asserts expiry.

7. **Documentation**
   `docs/infra/redis_queue.md` explains flag toggle, cost maths (€0.025 / hr) and contains runbook to re-enable queue within 5 min.

### Technical Notes / Steps

* **Terraform module** (`infra/redis/main.tf`)

  ```hcl
  resource "aws_elasticache_cluster" "queue" {
    count               = var.enable_redis ? 1 : 0
    cluster_id          = "tl-fif-queue"
    engine              = "redis"
    node_type           = "cache.t4g.small"
    num_cache_nodes     = 1
    parameter_group_name = "tl-fif-redis-6-2"
    subnet_group_name    = aws_elasticache_subnet_group.queue[0].name
    security_group_ids   = [aws_security_group.redis[0].id]
    at_rest_encryption_enabled = true
  }
  ```

* **CI Toggle Job** (`.github/workflows/toggle_redis.yml`)
  *Checks GPU CloudWatch metric `CPUUtilization`; if <1 % for 12 h, sets `ENABLE_REDIS=false` in `terraform.tfvars`, commits, then `terraform apply -auto-approve`.*

* **Cost Impact**: With flag true ≈ €18/mo; false €0 (only snapshots pennies).

---

## **RED-002 · `/queue-health` Diagnostics Lambda**

### Context

Operators need a cheap endpoint to confirm Redis is reachable and responding within SLA (< 200 ms p95). The Lambda runs in the same VPC, reuses Router’s security group, and is exposed via an **internal** API Gateway route (no JWT) restricted to VPC CIDR.

### Acceptance Criteria

1. **Lambda Implementation**

   * File `01_src/tinyllama/queue_health/handler.py`.
   * Executes `PING` and `LATENCY DOCTOR` using redis-py; measures round-trip.
   * Returns **200** `{"redis":"ok","latencyMs": <float>}` when latency < 200 ms.
   * Returns **503** `{"redis":"fail","error": "<msg>"}` otherwise.
   * Cold-start < 400 ms, memory 256 MB.

2. **API Integration**

   * New route `GET /queue-health` on existing HTTP API; `authorizer = NONE`.
   * Route is **VPC-CIDR-whitelisted** (`10.20.0.0/22`); external calls yield **403**.

3. **Alarm**

   * CloudWatch alarm `QueueHealthFail` triggers on **2 of 3** 5-min periods with 5xx.
   * Alarm action: PagerDuty + SNS.

4. **Tests**

   * Unit test with `fakeredis` simulates slow 300 ms response → expects 503.
   * Integration test in CI hits live dev Redis; asserts latency field.

5. **IaC**

   * Terraform `infra/lambda/queue_health.tf` with environment `REDIS_HOST`.
   * IAM role grants `elasticache:DescribeCacheClusters` (read-only) for future enhancements.

6. **Documentation**

   * `docs/ops/queue_health.md` shows sample curl, runbook steps if alarm fires.

### Technical Notes / Steps

* **Python snippet**

  ```python
  import os, time, redis, json
  r = redis.Redis(host=os.environ["REDIS_HOST"], socket_timeout=0.1)
  t0 = time.perf_counter()
  try:
      r.ping()
      latency = (time.perf_counter() - t0) * 1000
      if latency > 200:
          raise RuntimeError(f"High latency {latency:.1f}ms")
      return {"statusCode": 200,
              "body": json.dumps({"redis":"ok","latencyMs":round(latency,1)})}
  except Exception as exc:
      return {"statusCode": 503,
              "body": json.dumps({"redis":"fail","error":str(exc)})}
  ```

* **Cost**: < €0.10/mo (Lambda invocations and logs).

---

*Epic 5 (EC2) ticket expansions follow next.*

Below is the full-detail expansion for **Epic 5 – EC2 (Shape-Shifting Compute Node)**.
Four tickets (EC2-001 … 004) are now actionable at the same depth as earlier epics; next reply will begin Epic 6 (OPS).

---

## **EC2-001 · t3.small ↔ g4dn.xlarge Shape-Shifter Instance**

### Context

During idle periods a cheap **t3.small** sandbox keeps EBS state (\~€2/mo). When inference is requested, the node must resize to **g4dn.xlarge** GPU, serve requests, then shrink back or stop.  Audit gaps: EIP idle fees, AMI lookup ambiguity, and missing `ignore_changes` lifecycle.

### Acceptance Criteria

1. **Launch Template**

   * Uses latest Ubuntu 22.04 AMI via `aws_ami` data filter: `owner="099720109477"`, `name="ubuntu/images/*22.04-amd64-server-*"` sorted by creation date.
   * Root volume: gp3 30 GiB, encrypted, tag `Project=tinyllama`.
   * `instance_initiated_shutdown_behavior = "stop"`.

2. **EIP Management**

   * `aws_eip.elastic` attaches only when state `running`; lifecycle rule detaches and **releases** EIP when instance stops.
   * CloudWatch alarm `EIPIdle` (Detached > 1 h) -> SNS alert.

3. **Resize Mechanism**

   * `aws_ssm_document.ResizeInstance` runs `aws ec2 modify-instance-attribute --instance-type ${TARGET}`.
   * SSM IAM role limited to tag filter `Role=builder OR Role=gpu`.

4. **Terraform**

   * Instance resource has

     ```hcl
     lifecycle { ignore_changes = [instance_type] }
     ```

     so CI resize script doesn’t drift.

5. **Cost Controls**

   * Idle watchdog (EC2-003) must guarantee daily GPU hours ≤ 3 unless manual override.
   * Budget line item for EIP €3/mo shown in `costs.md`.

6. **Tests**

   * Terratest starts t3.small, runs SSM resize → g4dn.xlarge, verifies instanceType via `DescribeInstances`, then resizes back; assert total time < 4 min.
   * AWS Config rule `required-tags` ensures `Project` + `Role`.

### Technical Notes

* **Terraform** (snippet)

  ```hcl
  resource "aws_launch_template" "llama" {
    name_prefix   = "tinyllama-"
    image_id      = data.aws_ami.ubuntu.id
    instance_type = var.default_type # "t3.small"
    iam_instance_profile { name = aws_iam_instance_profile.gpu.name }
    tag_specifications {
      resource_type = "instance"
      tags = { Project = "tinyllama", Role = "gpu" }
    }
    user_data = filebase64("${path.module}/user_data/bootstrap.sh")
  }
  ```

* **Resize Script** (`04_scripts/ops/resize_instance.sh`) invoked by API (EC2-002).

* **AMI Cost**: snapshot \~8 GiB × €0.10 / mo = €0.80.

---

## **EC2-002 · `/resize` Admin API (start / stop / resize)**

### Context

Back-office admins trigger size changes through an authenticated route on the main HTTP API.  Must be Cognito‐group “admins” only, with full audit and rollback.

### Acceptance Criteria

1. **Route** `POST /resize`

   * Payload: `{"action":"start|stop|resize","target":"t3.small|g4dn.xlarge"}`.
   * Authorizer enforces JWT claim `groups contains "admins"`.

2. **Lambda Implementation** (`resize_handler.py`)

   * Validates input; maps to SSM document from EC2-001.
   * Publishes CloudWatch metric `ResizeRequests` with label `Action`.
   * Returns **202** `{"status":"accepted","operationId":<uuid>}`.

3. **IAM**

   * Execution role allows `ssm:SendCommand` on instance tag `Project=tinyllama`.
   * No direct `ec2:ModifyInstanceAttribute` permissions.

4. **Audit / Rollback**

   * All invocations logged to CloudTrail + Athena query `queries/resize_audit.sql`.
   * Runbook `docs/ops/resize_rollback.md` covers reverting mistaken resize in ≤ 2 min.

5. **Tests**

   * Unit: non-admin token → **403**.
   * Integration: send resize start→GPU, poll `DescribeInstances` until type matches.

### Technical Notes

* GUI “Stop GPU” button already wired to `/resize {"action":"stop"}`.
* Cost of Lambda negligible.

---

## **EC2-003 · Idle Self-Stop Watchdog (Local Cron)**

### Context

GPU time is billed per full minute; forgetting to shut it down is expensive.  A tiny local daemon must stop the instance after N minutes of zero inference activity.

### Acceptance Criteria

1. **Cron Spec**

   * Installed via cloud-init: `*/1 * * * * /opt/llama/idle_watch.sh >>/var/log/idle_watch.log 2>&1`.

2. **Logic** (`idle_watch.sh`)

   * Reads `/var/tmp/last_infer_ts`; if now − ts > `${IDLE_MIN:=300}` seconds → calls IMDS-v2 signed `POST /latest/api/token` then `ec2:StopInstances` self-call.

3. **Reliability**

   * Script exits non-zero on error; supervisord restarts on failure.
   * Logs shipped to CloudWatch under `/ec2/idle_watch`.

4. **Metrics**

   * `TLFIF/EC2/AutoStops` +1 on every triggered stop; used by OPS alarms.

5. **Tests**

   * Integration test in CI: run script with `IDLE_MIN=1`, confirm instance enters `stopping` within 90 s (non-GPU t3.micro).

6. **Security**

   * IAM profile limited to `ec2:StopInstances` \*\*Resource=arn\:aws\:ec2:*:*:instance/\${self}\`.

### Technical Notes

* Environment variable `IDLE_MIN` is set via userdata from GUI spin-box value.

---

## **EC2-004 · Docker Builder User-Data Bootstrap**

### Context

Building AMIs and Lambda layers on a GPU node is slow; a dedicated **builder** EC2 (t3.medium) boots on demand, installs Docker, SAM CLI, and CodeBuild agent, then auto-stops.  Prior audit required hardened user-data and CloudWatch piping.

### Acceptance Criteria

1. **User-Data Script** (`user_data/builder_boot.sh`)

   * Starts with `set -euo pipefail`.
   * Streams output via

     ```bash
     exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1
     ```
   * Installs Docker 25, `amazon-linux-extras enable docker`, adds `ec2-user` to group.
   * Installs SAM CLI 1.115 via RPM.

2. **CloudWatch Logs Agent**

   * Config file `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json` sends `/var/log/*` under `/ec2/builder`.

3. **Auto-Stop**

   * EventBridge rule `force-stop-build-runner` (already defined in IAM snippet) stops instance after 30 min running.

4. **AMI Tag & Trust**

   * Instance tag `Role=builder`; IAM profile from Epic 5 snippet (`build_runner_role.json`) attaches automatically.

5. **Tests**

   * CI Packer job spins builder AMI, runs `docker run hello-world`, returns 0.
   * Terratest asserts CloudWatch logs exist within 5 min of boot.

6. **Security**

   * SG ingress SSH 22 from corporate VPN CIDR only; egress 0/0 via NAT.

### Technical Notes

* Build scripts (`ci/ami_build.yml`) SSH into builder via SSM Session Manager; SSH port is backup.

---

### Epic 6 – OPS (Budgets & Observability Guardrails)

---

## **OPS-001 · Monthly Budget ≤ €20 & Auto-Killer at €21**

**Context**
Budget discipline is the final back-stop after all cost controls (idle timers, watchdogs) fail. AWS Budgets must raise early warnings at 75 % spend (\~€15) and invoke an automated killer Lambda at 105 % (€21) that stops the GPU node, releases the EIP, and deletes Redis if active. Previous audit flagged placeholder **subscriber {...}**, missing Lambda IaC and no recovery SOP.

**Acceptance Criteria**

1. **AWS Budgets** resource `aws_budgets_budget.tlfif_monthly` with `limit_amount = "20"` and `time_unit = "MONTHLY"`.
2. **Alert 75 %** → SNS topic `tlfif-budget-warn` (email + Slack webhook).
3. **Alert 105 %** → SNS topic `tlfif-budget-kill` triggers Lambda `budget_killer`.
4. **budget\_killer** Lambda (Python 3.12, 128 MB, 3 s timeout) runs:

   * `ec2:StopInstances` where `tag:Role=gpu`.
   * `eip:ReleaseAddress` for any detached EIP with tag `Project=tinyllama`.
   * `elasticache:DeleteCacheCluster` on `tl-fif-queue` when `enable_redis=false`.
   * Publishes CloudWatch metric `BudgetStops`.
5. **IAM role** scoped by tags; no wildcard ARNs.
6. **Rollback Runbook** (`docs/ops/budget_recovery.md`) describes restarting instance & re-attaching EIP in ≤ 5 min.
7. **Terratest**: set budget to €0.01, force breach, assert Lambda stops dummy t3.micro in dev account.
8. **Cost of Controls**: Budgets & SNS free; Lambda executions < €0.01/mo.

**Technical Notes**

* Terraform module `infra/ops/budget.tf` outputs SNS topic ARNs for reuse.
* Email subscriber set to `cost-alerts@yourdomain` (explicit—no placeholders).

---

## **OPS-002 · Unified CloudWatch Dashboard**

**Context**
Operators need a single “pane of glass” to correlate GPU utilisation, queue depth, latency, and daily spend. Prior audit lacked the actual dashboard JSON and a viewer IAM policy.

**Acceptance Criteria**

1. Terraform `aws_cloudwatch_dashboard.ops` name `TinyLlama-Overview`.
2. **Widgets (8)**:

   * GPU Util % (5 min, line)
   * GPU VRAM % (5 min, line)
   * Redis memory used (1 min, line)
   * API p95 latency (5 min, line)
   * Requests per minute (Lambda Router)
   * CurrentSpendEUR (bar, 1 h)
   * BudgetStops count (bar)
   * AutoStops count (bar)
3. Dashboard JSON stored at `observability/dashboard.json`; `cfn-lint` passes.
4. **Viewer IAM Policy** `CloudWatchReadOnlyTinyLlama` grants `cloudwatch:GetDashboard*` plus `GetMetricData` on `"TLFIF/*"` namespace only.
5. **CI Check**: GitHub Action `validate_dashboard.yml` parses JSON and ensures widget count ≥ 8.
6. **Load Test**: Opening dashboard in console renders in < 2 s (Cold start metric).
7. **Documentation** screenshot saved to `docs/ops/dashboard.png` for onboarding.

**Technical Notes**

* Use `stacked = false` for latency widget; `yAxis.right.min = 0` to avoid negative scale.

---

## **OPS-003 · Daily Cost Summary via SNS → Email**

**Context**
Stakeholders receive a 07:00 CET email with yesterday’s spend, projected month total, and top three cost drivers. Audit gaps: missing email body template, Cost Explorer API IAM, and Terraform resources.

**Acceptance Criteria**

1. **Lambda `cost_summary.py`** (256 MB, 30 s) executed by EventBridge rule `rate(1 day)` at 05:00 UTC.
2. Lambda calls `ce:GetCostAndUsage` (granularity = DAILY, metrics = "UnblendedCost") and composes Markdown email:

   ```
   TinyLlama Daily Cost – 2025-07-03
   Yesterday: €1.23
   Month-to-date: €8.90 / €20.00 (44 %)
   Projection: €19.8
   Top Drivers: EC2 €5.10, ElastiCache €2.50, CloudWatch €1.30
   ```
3. Publishes to SNS topic `tlfif-cost-daily`; email subscription `finance-team@yourdomain`.
4. IAM role allows `ce:GetCostAndUsage` and `sns:Publish` only.
5. **Unit tests** stub Cost Explorer, assert € projection calc.
6. **Integration test** in dev: Lambda writes to SNS FIFO (`content-based-deduplication=true`) to prevent duplicate mails.
7. **Alert**: if projection ≥ €18, email subject prefix “⚠️”.
8. **Cost**: Lambda & SNS < €0.05/mo.

**Technical Notes**

* Terraform `infra/ops/cost_summary.tf` sets `timezone = "Europe/Berlin"` for EventBridge schedule.

---

*Epic 7 (CI) ticket expansions will be delivered next.*
### Epic 7 – CI / CD Pipeline

---

## **CI-001 · Quality Gate — Lint → Unit → Lambda-Zip → Native-Wheel Guard**

**Context**
Every push to `main` or an open PR must fail fast if code quality or packaging rules regress. The pipeline runs entirely inside GitHub Actions on the free `ubuntu-22.04` runner and must finish in ≤ 4 minutes for incremental commits.

**Acceptance Criteria**

1. **Workflow File** `.github/workflows/ci.yml` triggered by `pull_request`, `push` on `main`.
2. **Steps (all cache-aware)**

   1. Checkout with `fetch-depth: 1`.
   2. Cache Poetry/pip with key on `hash(requirements.txt)`.
   3. `ruff check .` (no warnings).
   4. `pytest -q --cov=. --cov-report=xml` ≥ 90 % lines.
   5. Build Lambda package:

      ```bash
      zip -r router.zip 01_src/tinyllama/router
      ls -lh router.zip | awk '{exit ($5 > 5242880)}'
      ```

      *fails if > 5 MiB.*
   6. **Native-Wheel Guard** (script `ci/disallow_native.sh`) scans `site-packages` for `*.so`; error if any found.
3. **Artifacts**: `coverage.xml`, `router.zip` uploaded to run.
4. **Status Badge** in `README.md` green on passing.
5. **Fail-Fast**: `strategy.fail-fast: true`, pytest `--maxfail 1`.
6. **Terratest Matrix** (go test) runs in parallel job `integration` but only after quality gate passes.
7. Run time ≤ 4 min cold; measured in Actions summary.

**Technical Notes**

* Add `pre-commit` config identical to lint job so local hooks match CI.
* Cache invalidates when `requirements.txt` hash changes to avoid stale wheel scan.

---

## **CI-002 · SAM Build on Builder Node via SSM**

**Context**
Large Lambda container layers must be built on the **builder** EC2 (Epic 5) to avoid GitHub runner limits. GitHub Actions orchestrates the remote build over SSM, retrieves the artefact, and publishes to ECR/Lambda.

**Acceptance Criteria**

1. GitHub workflow `remote_build.yml` triggered by tag `v*.*.*`.
2. **Step order**

   1. Checkout & upload source to S3 `tlfif-build-src/<sha>.zip`.
   2. Invoke SSM `SendCommand` on instance tag `Role=builder` with document `TL-SAM-Build`:

      ```bash
      sam build --use-container -t template.yaml --cached
      sam package --s3-bucket tlfif-build-artifacts --output-template-file packaged.yaml
      aws lambda update-function-code --function tinyllama-router --s3-bucket tlfif-build-artifacts --s3-key lambda-router.zip
      ```
   3. Poll `CommandId` until `Success`.
   4. Download `packaged.yaml`, commit back to repo (opens PR).
3. Builder node self-stops via EventBridge when command complete.
4. End-to-end duration ≤ 12 min (AMI warm cache).
5. **IAM**: GitHub OIDC role `github-actions-ssm` limited to `ssm:SendCommand, ssm:GetCommandInvocation` on tag filter `Role=builder`.
6. **Cost Check**: Workflow logs monthly runtime in minutes; alarm if > 60 min/month.
7. **Tests**: Integration step asserts Lambda version increment via `GetAlias`.

**Technical Notes**

* `TL-SAM-Build` SSM document stored in `infra/ssm/build.yml` (YAML type `Command`).
* Use `aws-actions/configure-aws-credentials` with role `session-duration: 1800`.

---

## **CI-003 · End-to-End Smoke Test ≤ 120 s**

**Context**
Guarantees the whole public path (API → Lambda Router → Redis → GPU) works after every deploy. Must be non-blocking (marks pipeline *unstable* not *failed* if latency 90–120 s).

**Acceptance Criteria**

1. Job `smoke` runs after `deploy` in `remote_build.yml`.
2. Container image `python:3.12-slim`; installs `requests` only.
3. Steps

   1. Fetch base URL from Terraform output `api_url` (downloaded artefact).
   2. Generate test prompt `uuid4()`.
   3. `POST /infer` JWT from `CI_TEST_TOKEN` secret; expect `{"status":"queued"}`.
   4. Poll S3 `tlfif-responses/<uuid>.json` every 5 s, max 120 s.
   5. Fail if:

      * No object in 120 s.
      * JSON empty or `error` field present.
   6. Record total wall-clock seconds; emit metric `SmokeDuration`.
4. Action outcome mapping:

   * < 90 s → success.
   * 90–120 s → `continue-on-error: true`; job neutral; Slack warn.
   * > 120 s or error → pipeline **failed**.
5. Artefacts: saved response JSON + `timing.txt`.
6. **Cost**: Single inference uses g4dn.xlarge 2 min → €0.018.

**Technical Notes**

* JWT signed by dev Cognito user `smoke-bot`, rotated monthly via script `rotate_smoke_token.py`.
* Slack notification uses reusable workflow `notify.yml` with incoming webhook.

---

*All CI tickets are now fully expanded. Next epics (if any) are complete.*
