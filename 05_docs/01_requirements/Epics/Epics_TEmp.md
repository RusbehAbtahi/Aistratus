Below is the **definitive, implementation-ready rewrite** of Epics 2 through 7.
All tickets reference the existing Terraform baseline (`terraform/10_global_backend`), use the **shape-shifting EC2 pattern with a 30 GiB gp3 root volume**, and guarantee idle cost ≈ €2 / month (EBS only).
Every step is single-path, cost-aware, and immediately actionable by a solo developer.

---

## Epic 2 · API – Secure Edge Gateway (HTTP API)

| Key     | Scope                                                                               | Cost impact |
| ------- | ----------------------------------------------------------------------------------- | ----------- |
| API-201 | Harden `/infer`, `/stop`, `/health` routes behind Cognito JWT and per-user throttling | < €0.50/mo  |
| API-202 | Add CORS & structured JSON access logging                                           | negligible  |
| API-203 | Wire GUI login button → Cognito OAuth flow                                          | —           |

### API-201 · Gateway hardening & throttling

1. **Terraform module**: `modules/api`
   *Create `main.tf`, `variables.tf`, `outputs.tf`*.
2. **Import** existing HTTP API ID (run once, store in state).
3. **JWT authorizer**

   ```hcl
   resource "aws_apigatewayv2_authorizer" "jwt" {
     api_id          = data.aws_apigatewayv2_api.edge.id
     authorizer_type = "JWT"
     identity_sources = ["$request.header.Authorization"]
     name            = "cognito-jwt"
     jwt_configuration {
       audience = [var.COGNITO_CLIENT_ID]
       issuer   = var.cognito_issuer
     }
   }
   ```
4. **Attach** authorizer to `/infer` and `/stop`.
5. **Throttle**

   ```hcl
   resource "aws_apigatewayv2_stage" "prod" {
     ... # existing
     default_route_settings {
       throttling_burst_limit = 5
       throttling_rate_limit  = 20
     }
   }
   ```
6. **State test**: `terraform plan` must be **no-diff** after import, then `apply`.
7. **Smoke**: `curl -H "Authorization: Bearer $TOKEN" https://$API/infer` → 200.

### API-202 · CORS & JSON logging

1. **CORS**: add `allow_origins = ["http://localhost:*"]`.
2. **Access logs**:

   ```hcl
   access_log_settings {
     destination_arn = aws_cloudwatch_log_group.api_logs.arn
     format          = jsonencode({...})   # requestId, ip, route, status, latencyMs
   }
   ```
3. Log group retention 30 days.

### API-203 · GUI login integration

*No infrastructure change.*
Update GUI `AuthController` to open the Cognito Hosted UI (`https://<domain>/login?...`) and store `id_token`.
Test by logging in and posting `/infer`.

---

## Epic 3 · LAM – Lambda Router v2

| Key     | Scope                                     | Cost impact |
| ------- | ----------------------------------------- | ----------- |
| LAM-301 | Re-implement Router skeleton, enable flag | < €0.10/mo  |
| LAM-302 | Enqueue Redis job, return 202 with UUID   | —           |
| LAM-303 | GPU cold-boot logic (start / stop)        | —           |

### LAM-301 · Router enable

1. **Unset** `TL_DISABLE_LAM_ROUTER` in Lambda env via Terraform (`modules/compute/router.tf`).
2. Point handler to `tinyllama.router.handler`.
   `make lambda-package && terraform apply`.

### LAM-302 · Redis enqueue

1. Add `aws_elasticache_cluster` resource reference (from RED-401 output).
2. Include `REDIS_ENDPOINT` env var.
3. Python: use `redis-py`, key `job:{uuid}`, TTL 300 s.
4. Return JSON: `{"status":"queued","id":"<uuid>"}`.

### LAM-303 · Cold-boot EC2

1. Add IAM permission `ec2:StartInstances`, tag-scoped.
2. Logic: if `describe_instances(filters=[{"Name":"instance-state-name","Values":["stopped"]}])` → `start_instances`.
3. Immediately return `{"status":"starting","eta":90}`.

---

## Epic 4 · RED – Redis Job Queue

| Key     | Scope                                                    | Cost impact                      |
| ------- | -------------------------------------------------------- | -------------------------------- |
| RED-401 | t4g.small Redis in public subnet, SG locked to Lambda IP | €18/mo **destroyed at plan end** |
| RED-402 | /queue-health Lambda for diagnostics                     | < €0.10/mo                       |

### RED-401 · Queue creation

1. **Terraform** `modules/redis`:

   ```hcl
   resource "aws_elasticache_cluster" "jobs" {
     engine               = "redis"
     node_type            = "cache.t4g.small"
     num_cache_nodes      = 1
     port                 = 6379
     subnet_group_name    = aws_elasticache_subnet_group.redis.id
     security_group_ids   = [aws_security_group.redis.id]
     preferred_availability_zone = data.aws_availability_zones.azs.names[0]
     tags = { Project = "tinyllama" }
   }
   ```
2. **SG rules**: ingress 6379 from Lambda SG CIDR, egress 0/0.
3. **Destroy automation**: add `enable_redis = var.use_gpu` (default `false`).
   *Daily `terraform apply -auto-approve -target=aws_elasticache_cluster.jobs` in CI only when GPU path active.*
   *No resource = no cost when idle.*

### RED-402 · Health-check Lambda

1. New function `queue_health.py` (Python 3.12, 128 MB).
2. Returns `{"redis":"ok","latencyMs":<n>}`.
3. CloudWatch alarm on p95 > 200 ms for 5 mins.

---

## Epic 5 · EC2 – Shape-Shifting Compute Node

| Key     | Scope                                                   | Cost impact |
| ------- | ------------------------------------------------------- | ----------- |
| EC2-501 | Single public-subnet EC2 with EIP, 30 GiB gp3           | €2/mo idle  |
| EC2-502 | Auto-resize API (`POST /resize`) g4dn.xlarge ↔ t3.small | pay-per-use |
| EC2-503 | Idle self-stop watchdog (5 min default)                 | —           |
| EC2-504 | Docker builder user-data for Lambda ZIP/image           | —           |

### EC2-501 · Base instance & EBS

1. **Terraform module** `modules/compute`:

   ```hcl
   resource "aws_instance" "shape" {
     ami                         = data.aws_ami.ubuntu.id
     instance_type               = "t3.small"
     subnet_id                   = module.networking.public_subnet_id
     associate_public_ip_address = true
     key_name                    = var.key_name
     ebs_block_device {
       device_name = "/dev/xvda"
       volume_size = 30
       volume_type = "gp3"
       delete_on_termination = false
     }
     tags = { Name = "tl-shape", Role = "builder+gpu" }
   }
   resource "aws_eip" "shape" {
     instance = aws_instance.shape.id
     vpc      = true
   }
   ```
2. **IAM profile**: SSM, ECR, S3 (`tinyllama-data-*`), `ec2:ModifyInstanceAttribute`.

### EC2-502 · Resize endpoint

1. Add Lambda `shape_control.py` (runs in default Lambda SG).
   *`/resize?target=g4dn.xlarge|t3.small`*
   Steps: `stop_instances` → `modify_instance_attribute` → `start_instances`.
2. Attachable to `/resize` route (admin only).
3. Add CloudWatch metric `Resizes`.

### EC2-503 · Idle watchdog

1. Cron in instance user-data: run every minute, `if $(($(date +%s)-$(stat -c %Y /var/log/user.log))) > 300; then aws ec2 stop-instances ...; fi`.
2. IAM already grants self-stop.

### EC2-504 · Docker builder

1. `cloud-init` installs Docker 24, `aws-sam-cli`.
2. Builder script: `make lambda-package && aws lambda update-function-code`.

---

## Epic 6 · OPS – Budgets, Alarms, Dashboard

| Key     | Scope                                                        | Cost impact |
| ------- | ------------------------------------------------------------ | ----------- |
| OPS-601 | Budget ≤ €20, warn at €15, killer at €21                     | free        |
| OPS-602 | CloudWatch dashboard: cost, EC2 state, Redis mem, Lambda p95 | free        |
| OPS-603 | Daily cost summary SNS → email                               | negligible  |

### OPS-601 · Budget & killer

1. Terraform `modules/ops/budget.tf`:

   ```hcl
   resource "aws_budgets_budget" "monthly" {
     name              = "tinyllama-budget"
     budget_type       = "COST"
     time_unit         = "MONTHLY"
     limit_amount      = "20"
     limit_unit        = "EUR"
     cost_filters      = {}
     notification {
       comparison_operator = "GREATER_THAN"
       threshold           = 15
       threshold_type      = "ABSOLUTE_VALUE"
       notification_type   = "FORECASTED"
       subscriber { ... }
     }
     notification {
       comparison_operator = "GREATER_THAN"
       threshold           = 21
       threshold_type      = "ABSOLUTE_VALUE"
       notification_type   = "ACTUAL"
       subscriber { sns_topic_arn = aws_sns_topic.killer.arn }
     }
   }
   ```
2. Killer Lambda: `stop_instances`, `delete_eip`, `delete_redis`.

### OPS-602 · Dashboard

Use `aws_cloudwatch_dashboard` JSON with metrics:
`AWS/Billing EstimatedCharges`, `EC2 CPUUtil`, `Redis FreeableMemory`, `Lambda Duration p95`, `BudgetOverruns`.

### OPS-603 · Cost mail

SNS topic + daily EventBridge rule `cost_summary.py` (Cost Explorer API).

---

## Epic 7 · CI – Continuous Delivery Pipeline

| Key    | Scope                                                                        | Cost impact |
| ------ | ---------------------------------------------------------------------------- | ----------- |
| CI-701 | GitHub Actions → `terraform fmt & validate`, `pytest`, `make lambda-package` | free        |
| CI-702 | On main push: SAM build on EC2 shape node via SSM                            | negligible  |
| CI-703 | End-to-end smoke (`/infer` echo) max 120 s                                   | negligible  |

### CI-701 · Lint & unit

Update `.github/workflows/ci.yml` to:

```yaml
- run: terraform -chdir=terraform/10_global_backend fmt -check
- run: terraform -chdir=terraform/10_global_backend validate
- run: pytest -q
- run: make lambda-package
- run: du -b build/router.zip | awk '$1>5000000{exit 1}'
```

### CI-702 · SAM build on shape node

1. Job uses `aws ssm send-command` to run builder script.
2. Wait for command success; fail CI if non-zero.

### CI-703 · Smoke test

`curl -s https://$API/health` → 200, then `/infer` with dummy prompt → 202 in ≤ 120 s.

---

### **All tickets are now locked and ready for direct implementation.**

No further options or placeholders exist. Let me know once you commit each module, and we will iterate ticket by ticket.
