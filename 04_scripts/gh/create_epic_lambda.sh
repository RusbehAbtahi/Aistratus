#!/bin/bash

# LAM-001 – Enable Router & Real JWT / Body Validation
gh issue create -t "LAM-001 · Enable Router & Real JWT / Body Validation" -l "lambda,story" -b "Parent: #57

### Context

\`tinyllama-router\` is currently disabled in prod via \`TL_DISABLE_LAM_ROUTER=\"1\"\`. We must flip that flag, hard-wire JWT verification identical to API-003, and validate the JSON body (\`prompt\`, \`idle\`) before spending Redis/EC2 cost. Prior audits flagged missing rollback steps and unclear CI packaging.

### Acceptance Criteria

1. **Activation**
   - Terraform sets \`environment { variables = { TL_DISABLE_LAM_ROUTER = \"0\" } }\`.
   - \`terraform apply\` publishes new version, shifts alias **prod**; previous 5 versions retained (automated via Lambda alias/versions).
2. **JWT Verification**
   - Uses shared lib \`tinyllama.utils.auth.verify_jwt(token, issuer, aud)\` (import path matches \`jwt_tools.py\`).
   - Invalid JWT → **401**, body \`{\"error\":\"invalid_token\"}\`; latency ≤ 100 ms (cold ≤ 350 ms).
3. **Schema Validation**
   - Request JSON must match:
     \`\`\`json
     { \"prompt\": \"<string 1-6 kB>\", \"idle\": <int 1-30> }
     \`\`\`
   - Exceeding limits → **400** with field-specific error.
   - Validation performed via \`pydantic\` model; code coverage ≥ 95% on model/handler.
4. **Rollback**
   - \`make lambda-rollback VERSION=\$PREV\` script documented; RUNBOOK section added to \`docs/ops/lambda_router.md\`.
   - GitHub Action \`router_canary.yml\` hits \`/ping\` every 5 min; two failures trigger auto-rollback via \`aws lambda update-alias --function-name tinyllama-router --name prod --function-version \$PREV\`.
5. **Tests** (CI job \`lam_router_spec\`)
   - Unit tests: happy path, >6 kB prompt, idle=0, tampered JWT.
   - Contract test runs \`sam local invoke\` with Docker to ensure env var wired.
   - p95 duration in X-Ray segment must be < 60 ms warm.

### Technical Notes / Steps

- **Terraform** (\`infra/lambda/router.tf\`)
  \`\`\`hcl
  resource \"aws_lambda_function\" \"router\" {
    filename         = data.archive_file.router_zip.output_path
    handler          = \"tinyllama.router.handler.lambda_handler\"
    runtime          = \"python3.12\"
    memory_size      = 512
    timeout          = 30
    environment {
      variables = {
        TL_DISABLE_LAM_ROUTER = \"0\"
        COGNITO_ISSUER        = var.cognito_issuer
        COGNITO_AUD           = var.cognito_app_client_id
      }
    }
    layers = [aws_lambda_layer_version.shared_deps.arn]
    tracing_config { mode = \"Active\" }
  }
  \`\`\`
- **Python skeleton** (\`01_src/tinyllama/router/handler.py\`)
  \`\`\`python
  from tinyllama.utils.auth import verify_jwt
  from tinyllama.utils.schema import PromptReq

  def lambda_handler(evt, ctx):
      hdr = evt[\"headers\"].get(\"authorization\",\"\")
      token = hdr.removeprefix(\"Bearer \")
      verify_jwt(token, os.environ[\"COGNITO_ISSUER\"],
                 os.environ[\"COGNITO_AUD\"])
      body = PromptReq.model_validate_json(evt[\"body\"])
      # enqueue logic in next ticket …
      return {\"statusCode\":202,\"body\":'{\"status\":\"queued\"}'}
  \`\`\`
- **Cost impact**: +€0.10/mo (extra Lambda invocations, X-Ray traces).
"

# LAM-002 – Redis Enqueue with 5-Minute TTL
gh issue create -t "LAM-002 · Redis Enqueue with 5-Minute TTL" -l "lambda,story" -b "Parent: #57

### Context

Router must place validated jobs into Redis (see RED-001) using a strict schema and auto-expire orphaned entries after 300 seconds. Prior audit demanded error fallback and SG verification.

### Acceptance Criteria

1. **Enqueue Logic**
   - Key pattern: \`job:{uuid}\`.
   - Value JSON contains \`prompt\`, \`idle\`, \`reply_s3\`, \`ts\`.
   - \`EX 300\` set atomically (\`SET key val EX 300 NX\`).
2. **Happy Path**
   - Returns **202** \`{\"status\":\"queued\",\"id\":\"<uuid>\"}\` ≤ 60 ms warm.
3. **Failure Handling**
   - Redis timeout or auth failure → **503** \`{\"error\":\"queue_unavailable\"}\`; CloudWatch metric \`RedisEnqueueFail\`+1.
   - No retry inside Lambda (caller decides).
4. **Security**
   - Lambda SG allows egress to Redis SG 6379 only; verified in terratest (\`tests/sg_ingress_test.go\`).
5. **Tests**
   - Unit test with \`fakeredis\` asserts TTL between 295–305 s.
   - Integration test in CI uses real ElastiCache endpoint in dev account (tag-scoped IAM).

### Technical Notes

- **Python** enqueue snippet (add to handler):
  \`\`\`python
  import redis, uuid, json, os, boto3, time
  r = redis.Redis(host=os.environ[\"REDIS_HOST\"], port=6379,
                  socket_timeout=0.05)
  jid = str(uuid.uuid4())
  job = {\"prompt\": body.prompt,
         \"idle\": body.idle,
         \"reply_s3\": f\"s3://{os.environ['REPLY_BUCKET']}/{jid}.json\",
         \"ts\": int(time.time()*1000)}
  if not r.set(f\"job:{jid}\", json.dumps(job), ex=300, nx=True):
      raise RuntimeError(\"Job collision\")
  return {\"statusCode\":202,\"body\":json.dumps({\"status\":\"queued\",\"id\":jid})}
  \`\`\`
- **Alarm**: CloudWatch alarm \`RedisEnqueueFail >=3 in 5m\` → SNS \`#tinyllama-alerts\`.
- **Cost**: Redis additional commands negligible; CloudWatch metrics ≈ €0.02/mo.
"

# LAM-003 – GPU Cold-Boot Logic
gh issue create -t "LAM-003 · GPU Cold-Boot Logic" -l "lambda,story" -b "Parent: #57

### Context

If the GPU EC2 instance (see EC2-001) is **stopped**, Router must start it and immediately inform GUI of a ~90 s ETA. Audit noted missing metric and unclear client-poll strategy.

### Acceptance Criteria

1. **Start Decision**
   - Router queries EC2 by tag \`Project=tinyllama\` && \`Role=gpu-node\`.
   - If state \`stopped|stopping|terminated\` → call \`start_instances\`.
   - If state \`pending|running\` → skip start.
2. **Immediate Response**
   - When a cold start is triggered, Router returns **202** \`{\"status\":\"starting\",\"eta\":90}\` and header \`X-GPU-ColdBoot:true\`.
   - GUI must poll \`/ping\` until 200.
3. **Metrics**
   - \`EC2Starts\` (Dim:Reason=ColdBoot) \`PutMetricData\` on every start.
   - p95 start_instances API latency ≤ 400 ms.
4. **Idempotency**
   - Second request during \`pending\` state must *not* call start again; still returns \`starting\`.
5. **Tests**
   - Unit test with \`botocore.stub.Stubber\` asserts tag filter & idempotency.
   - CI integration test starts a t3.micro in dev to avoid GPU billing; checks metric emission.
6. **Rollback Safety**
   - If Lambda fails to start instances (limit, insufficient capacity), returns **503** with error details; GUI shows toast.

### Technical Notes

- **Python** excerpt:
  \`\`\`python
  ec2 = boto3.client(\"ec2\")
  res = ec2.describe_instances(Filters=[
      {\"Name\":\"tag:Project\",\"Values\":[\"tinyllama\"]},
      {\"Name\":\"tag:Role\",\"Values\":[\"gpu-node\"]}
  ])
  iid = res[\"Reservations\"][0][\"Instances\"][0][\"InstanceId\"]
  state = res[\"Reservations\"][0][\"Instances\"][0][\"State\"][\"Name\"]
  if state == \"stopped\":
      ec2.start_instances(InstanceIds=[iid])
      cw.put_metric_data(
          Namespace=\"TLFIF\",
          MetricData=[{\"MetricName\":\"EC2Starts\",\"Value\":1,
                       \"Unit\":\"Count\",\"Dimensions\":[
                           {\"Name\":\"Reason\",\"Value\":\"ColdBoot\"}]}])
      return _starting_response()
  elif state in (\"pending\",\"running\"):
      return _starting_response() if state==\"pending\" else _normal_flow()
  else:
      return _error(\"instance_unavailable\")
  \`\`\`
- **Cost**: start API free; GPU uptime cost accounted in EC2 epic.
"

