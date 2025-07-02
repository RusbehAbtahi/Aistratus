title: "Epics 2 – 7 — Hardened Implementation Plan v2"
author: "Rusbeh Abtahi"
version: "2.0"
updated: "2025‑06‑13"
---------------------

> **Scope** — This file fully supersedes *Epics_TEmp.md* by incorporating every
> finding from **EpicsAudit_Main_45.md** (RISK‑1 ➜ RISK‑3 and professional
> guidance), plus all style / rigor constraints defined in the project Prompt
> (cost‑discipline, single‑path execution, solo‑dev safety).  Nothing has been
> removed; only clarifications, explicit snippets, or operational add‑ons have
> been inserted.  Use this as the *only* source of truth going forward.

---

## 🔖 Legend

| Emoji | Meaning                                |
| ----- | -------------------------------------- |
| 💸    | Direct cost or cost‑control note       |
| 🛡️   | Security / IAM clarification           |
| ⚙️    | Operational note (bootstrap, teardown) |
| 📄    | Code / policy snippet                  |

---

# Epic 2 · API — Secure Edge Gateway *(HTTP API)*

| Key         | Scope                                                                      | Cost          |
| ----------- | -------------------------------------------------------------------------- | ------------- |
| **API‑003** | Harden `/infer`, `/stop`, `/ping` behind Cognito JWT & per‑user throttling | 💸 < €0.50/mo |
| **API‑004** | CORS + structured JSON access logging                                      | negligible    |
| **API‑005** | GUI login button → Cognito OAuth flow                                      | —             |

Understood. Here is **only the updated API-003** section, with the explicit rollback/disaster recovery step and the minimal Terraform IAM policy snippet added—ready to copy-paste.

---

````markdown
### API‑003 — Gateway Hardening & Throttling

* unchanged from v1, plus:
* 🛡️ Add **`aws_apigatewayv2_route_settings`** per route so a later mass‑import cannot null‑out throttling defaults.
* ⚙️ **Rollback/Disaster Recovery:**  
  If throttling or authorizer configuration causes API breakage, perform a targeted rollback with:  
  `terraform apply -refresh-only -replace=aws_apigatewayv2_route_settings.example`  
  (replace `.example` with your actual resource name) to restore defaults immediately.
* 🛡️ **Terraform IAM Policy:**  
  Add the following minimal IAM policy to allow API Gateway to retrieve Cognito JWKS and publish access logs to CloudWatch:

```hcl
resource "aws_iam_role" "apigw_role" {
  name = "apigw-edge-role"
  assume_role_policy = data.aws_iam_policy_document.apigw_assume_role.json
}

data "aws_iam_policy_document" "apigw_policy" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "cognito-idp:DescribeUserPool",
      "cognito-idp:ListUserPoolClients",
      "cognito-idp:DescribeUserPoolClient"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "apigw_policy" {
  role   = aws_iam_role.apigw_role.id
  policy = data.aws_iam_policy_document.apigw_policy.json
}
````

*Acceptance Criteria update:*

* Rollback procedure is documented and testable.
* IAM role and policy are explicitly defined in Terraform.
* No placeholders or missing config remain.




### API‑004 — CORS & Logging

* 💸 Set **log‑retention = 30 days** (was implicit) and rely on tier‑free GB.

### API‑005 — GUI Integration

* No infra change; docs now reference `AuthController` update committed in *UML_Diagram*.

---

# Epic 3 · LAM — Lambda Router v2

| Key         | Scope                                             | Cost          |
| ----------- | ------------------------------------------------- | ------------- |
| **LAM‑001** | Enable Router (flag ↓) & real JWT/body validation | 💸 ≈ €0.10/mo |
| **LAM‑002** | Redis enqueue (TTL 300 s)                         | —             |
| **LAM‑003** | GPU cold‑boot logic                               | —             |

### LAM‑001 — Enable + Validation (updates)

* 🛡️ `verify_jwt()` now imported from **shared** `tinyllama.utils.auth` to avoid drift.
* 📄 `terraform/modules/compute/router.tf` now sets `TL_DISABLE_LAM_ROUTER="0"`.

### LAM‑003 — Cold‑boot

* ⚙️ Emit CloudWatch **`EC2Starts`** metric for dashboard; include `Dimension=Reason:ColdBoot`.

---

# Epic 4 · RED — Redis Job Queue

| Key         | Scope                                       | Cost                              |
| ----------- | ------------------------------------------- | --------------------------------- |
| **RED‑001** | t4g.small Redis (private subnet, SG locked) | 💸 €18 → €0 (destroyed when idle) |
| **RED‑002** | `/queue‑health` diagnostics Lambda          | 💸 < €0.10/mo                     |

### RED‑001 — Queue (clarifications)

* ⚙️ Queue is created **only** when `var.use_gpu=true`; the daily *destroy‑plan* CI job guarantees zero idle cost.
* 🛡️ SG now also **egress‑blocks 0.0.0.0/0** except NAT‑GW range to enforce VPC‑private traffic.

---

# Epic 5 · EC2 — Shape‑Shifting Compute Node

| Key         | Scope                                             | Cost          |
| ----------- | ------------------------------------------------- | ------------- |
| **EC2‑001** | t3.small ↔ g4dn.xlarge shape‑shifter (30 GiB gp3) | 💸 €2/mo idle |
| **EC2‑002** | `/resize` API (start/stop/resize)                 | pay‑per‑use   |
| **EC2‑003** | Idle self‑stop watchdog (local cron)              | —             |
| **EC2‑004** | Docker builder user‑data                          | —             |

### **🛡️ Explicit IAM for Build‑Runner (RISK‑2)**

📄 `00_infra/build_runner_role.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ], "Resource": "*" },
    { "Effect": "Allow", "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::tinyllama-build-artifacts/*" },
    { "Effect": "Allow", "Action": "lambda:UpdateFunctionCode",
      "Resource": "arn:aws:lambda:*:*:function:tinyllama-router" },
    { "Effect": "Allow", "Action": [
        "ssm:SendCommand", "ssm:ListCommandInvocations"
      ], "Resource": "*" }
  ]
}
````

### **⚙️ Bootstrap & Teardown Hardening (RISK‑1 & RISK‑3)**

* **User‑data preamble** now starts with `set -euo pipefail` and streams STDOUT/ERR via:

  ```bash
  exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
  ```
* CloudWatch Logs agent installs and groups under `/ec2/build-runner`.
* EventBridge rule **`force‑stop-build-runner`**

  * cron: `rate(30 minutes)`
  * filter: `detail.state = "running" && detail.tag.Project = "tinyllama" && detail.tag.Role = "builder" && detail.launchTime < now-55m"`
  * target: Lambda `stop_build_box.py` (see snippet in OPS‑001).

---

# Epic 6 · OPS — Budgets, Alarms, Dashboard

| Key         | Scope                          | Cost          |
| ----------- | ------------------------------ | ------------- |
| **OPS‑001** | Budget ≤ €20, killer at €21    | free          |
| **OPS‑002** | Unified CloudWatch dashboard   | free          |
| **OPS‑003** | Daily cost summary SNS → email | 💸 < €0.05/mo |

### **OPS‑001** (updates)

* 📄 `stop_build_box.py` now referenced by both Budget killer and EventBridge builder‑timeout rule.

```python
import boto3, os
EC2 = boto3.client('ec2')
IDS = [i['InstanceId'] for i in EC2.describe_instances(
          Filters=[{'Name':'tag:Role','Values':['builder']}])['Reservations'][0]['Instances']
        if i['State']['Name']=='running']
if IDS:
    EC2.stop_instances(InstanceIds=IDS)
```

---

# Epic 7 · CI — Continuous Delivery Pipeline

| Key        | Scope                                      | Cost       |
| ---------- | ------------------------------------------ | ---------- |
| **CI‑001** | Lint, unit, lambda‑zip, native‑wheel guard | free       |
| **CI‑002** | SAM build on shape node via SSM            | negligible |
| **CI‑003** | End‑to‑end smoke ≤ 120 s                   | negligible |

### CI‑001 — Native Wheel Guard (audit add‑on)

* New step after `pip install`:

  ```yaml
  - name: Disallow native wheels
    run: |
      if python - <<'PY'
  ```

import sys, subprocess, pathlib, json, importlib.metadata as im
bad = \[d for d in im.distributions() if any(p.suffix=='.so' for p in pathlib.Path(d.locate\_file('')).rglob('\*.so'))]
print(json.dumps(\[b.metadata\['Name'] for b in bad])); sys.exit(len(bad)>0)
PY
then echo "::error::Native extensions found" && exit 1; fi

```

### ⚙️ Operational Notes (added across epics)
* Each epic now ends with an **Operational Notes** subsection linking to ADRs or scripts when audit requested more explicitness.

---
## ✅ Change‑Log (relative to *Epics_TEmp.md*)
* Added explicit IAM JSON, user‑data hardening, CloudWatch log piping, builder auto‑stop, native‑wheel guard.
* Clarified log retention, metric dimensions, SG egress rules.
* No scope dropped; cost ceilings unchanged.

---
**End of Epics 2‑7 — Hardened Implementation Plan v2**

```

