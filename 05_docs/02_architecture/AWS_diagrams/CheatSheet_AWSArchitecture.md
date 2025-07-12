Absolutely. Here’s a **fully revised CheatSheet\_AWSArchitecture.md**
—with all improvements from the audit, explicit ARNs/IDs, CI/CD IAM documentation, VPC clarifications, automation tips, alarm details, and clear legacy flags.

---

````markdown
# 🦙 TinnyLlama Project Cheat Sheet & AWS Architecture

---

## 🚀 Quick Command Cheat Sheet

```bash
cd /c/0000/Prompt_Engineering/Projects/GTPRusbeh/Aistratus
cd /c/0000/Prompt_Engineering/Projects/GTPRusbeh/Aistratus/terraform/10_global_backend
source .venv/Scripts/activate

cd /c/0000/Prompt_Engineering/Projects/GTPRusbeh/Aistratus/01_src/lambda_layers/shared_deps
python build_layer_ci.py

cd /c/0000/Prompt_Engineering/Projects/GTPRusbeh/Aistratus/terraform/10_global_backend
terraform init -reconfigure
terraform validate
terraform plan -var="env=default" -var="artifact_bucket=tinyllama-data-108782059508"
terraform apply -var="env=default" -var="artifact_bucket=tinyllama-data-108782059508"

terraform import -var="env=default" -var="artifact_bucket=tinyllama-data-108782059508" \
  'module.compute.module.iam.aws_iam_role.router' tlfif-default-router

# Get all current Terraform outputs as a Markdown table
terraform output -json | jq -r '. | to_entries[] | "| `\(.key)` | \(.value.value) |"' > terraform_outputs.md
````

---

## 🌍 AWS Overview & Important IDs

| Resource/ID/Value                                                                    | Description / Purpose                              |
| ------------------------------------------------------------------------------------ | -------------------------------------------------- |
| `eu-central-1`                                                                       | AWS region (Frankfurt)                             |
| `108782059508`                                                                       | AWS Account ID                                     |
| `tinyllama-data-108782059508`                                                        | S3 bucket for Lambda layer/artifacts               |
| `vpc-02268c8b6bfc3bf39`                                                              | Primary VPC ID (CIDR: 10.20.0.0/22)                |
| `tlfif-default-router`                                                               | IAM role for Lambda Router (per env, e.g. default) |
| `arn:aws:iam::108782059508:role/tlfif-default-router`                                | Lambda Router IAM Role ARN                         |
| `tlfif-default-shared-deps`                                                          | Lambda Layer name (per environment)                |
| `arn:aws:lambda:eu-central-1:108782059508:layer:tlfif-default-shared-deps:<version>` | Layer ARN                                          |
| `/tinyllama/default/*`                                                               | SSM Parameter Store root for "default" env         |
| Cognito Pool IDs                                                                     | `eu-central-1_D3uD0a6nN`, `eu-central-1_FvUbA75NY` |
| SQS Queue                                                                            | \[Planned] Add actual ARN/URL once created         |
| Lambda ARN                                                                           | (get via Terraform output or AWS console)          |

---

## 🔒 CI/CD IAM Roles & Policies

| CI/CD IAM Resource      | ARN                                                       | Policies (Summary)                |
| ----------------------- | --------------------------------------------------------- | --------------------------------- |
| GitHub Actions Deployer | arn\:aws\:iam::108782059508\:role/github-actions-deployer | CW Logs, Lambda, S3, SSM, Deploy  |
| Lambda Router Role      | arn\:aws\:iam::108782059508\:role/tlfif-default-router    | Lambda exec, SSM, SQS, CloudWatch |

---

## 🗂️ Project Directory Tree (Essentials Only)

```
/c/0000/Prompt_Engineering/Projects/GTPRusbeh/Aistratus
├── 01_src
│   ├── lambda_layers
│   │   └── shared_deps
│   │       ├── build_layer_ci.py
│   │       ├── requirements.txt
│   │       ├── shared_deps.zip
│   │       └── python/
│   └── tinyllama
│       ├── gui/
│       ├── router/
│       └── utils/
├── terraform
│   └── 10_global_backend
│       ├── backend.tf
│       ├── ci_role.tf
│       ├── locals_ids.tf
│       ├── main.tf
│       ├── outputs.tf
│       ├── variables.tf
│       ├── modules
│       │   ├── core
│       │   │   ├── auth/
│       │   │   ├── networking/
│       │   │   └── ssm_params/
│       │   ├── observability
│       │   │   └── monitoring/
│       │   └── services
│       │       ├── compute/
│       │       ├── iam_router/
│       │       └── lambda_layers/
```

---

## 📐 Improved AWS Architecture Map

```text
                      🌐 AWS (eu-central-1, Account: 108782059508)
                                     │
                   ┌─────────────────┴───────────────────┐
                   │                                     │
             🛡️ VPC (CIDR: 10.20.0.0/22, ID: vpc-02268c8b6bfc3bf39)
                   │
         ┌─────────┴──────────┐
         │                    │
 🔑 Private Subnets      🔒 Security Groups
         │                    │
         └─────┬──────────────┘
               │
       🦙 Lambda Function
    Name: tlfif-default-router
    ARN: arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router
               │
               │───────🧑‍🚀 IAM Role: arn:aws:iam::108782059508:role/tlfif-default-router
               │                (Lambda exec, CW Logs, SSM, SQS)
               │
               │───────📚 Lambda Layer
               │         Name: tlfif-default-shared-deps
               │         ARN: arn:aws:lambda:eu-central-1:108782059508:layer:tlfif-default-shared-deps:<version>
               │         ZIP: shared_deps.zip (Python, local build)
               │
               ├───────🔐 AWS SSM Parameter Store
               │         Path: /tinyllama/default/*
               │         Params: COGNITO_POOL_ID, CLIENT_ID, ISSUER, SQS_QUEUE_URL...
               │
               ├───────🔑 Cognito Pools
               │         eu-central-1_D3uD0a6nN, eu-central-1_FvUbA75NY
               │
               ├───────📊 CloudWatch Logs
               │         Log Group: /aws/lambda/tlfif-default-router
               │
               ├───────🔔 CloudWatch Metric Alarm
               │         Alarm: tlfif-default-router-p95-latency (>60ms)
               │         ARN: arn:aws:cloudwatch:eu-central-1:108782059508:alarm:tlfif-default-router-p95-latency
               │
               ├───────📦 S3 Bucket: tinyllama-data-108782059508
               │         Stores: Lambda layer zips, artifacts
               │
               └───────📨 SQS Queue (Planned)
                         Name/ARN: [Add after creation]
```

---

## 📝 SSM Parameter Store Variables (with status)

| Parameter Name / Path                  | Purpose / Description                            | Example Value / Note                                                                    | Status     |
| -------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------- | ---------- |
| `/tinyllama/default/COGNITO_POOL_ID`   | Cognito User Pool ID for the environment         | `eu-central-1_D3uD0a6nN`                                                                | In use     |
| `/tinyllama/default/COGNITO_CLIENT_ID` | Cognito App Client ID (JWT audience)             | `xyzclientid`                                                                           | In use     |
| `/tinyllama/default/COGNITO_ISSUER`    | OIDC issuer URL for Cognito auth                 | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_D3uD0a6nN`                 | In use     |
| `/tinyllama/default/SQS_QUEUE_URL`     | SQS queue URL for async queueing                 | (To be filled after SQS creation)                                                       | Planned    |
| `/tinyllama/default/SQS_QUEUE_ARN`     | SQS queue ARN                                    | (To be filled after SQS creation)                                                       | Planned    |
| `/tinyllama/default/ENV`               | Environment marker                               | `default`                                                                               | In use     |
| `/tinyllama/default/ROUTER_LAMBDA_ARN` | ARN of deployed Router Lambda                    | arn\:aws\:lambda\:eu-central-1:108782059508\:function\:tlfif-default-router             | In use     |
| `/tinyllama/default/LAYER_ARN`         | ARN of shared\_deps Lambda Layer                 | arn\:aws\:lambda\:eu-central-1:108782059508\:layer\:tlfif-default-shared-deps:<version> | In use     |
| `/tinyllama/default/REDIS_HOST`        | \[Deprecated] Previously used for Redis endpoint | *Replaced by SQS, can be removed*                                                       | Deprecated |

---

## 📊 CloudWatch Alarms (Details)

| Alarm Name                       | Metric                | Threshold | ARN                                                                                      | Notes                   |
| -------------------------------- | --------------------- | --------- | ---------------------------------------------------------------------------------------- | ----------------------- |
| tlfif-default-router-p95-latency | Lambda Duration (p95) | >60ms     | arn\:aws\:cloudwatch\:eu-central-1:108782059508\:alarm\:tlfif-default-router-p95-latency | Monitors router latency |

---

## 🛡️ Automation/Outputs Tip

* **Always export Terraform outputs after apply:**

  ```bash
  terraform output -json | jq -r '. | to_entries[] | "| `\(.key)` | \(.value.value) |"' > terraform_outputs.md
  ```

  Then copy relevant ARNs/IDs into this cheat sheet.

* **Keep all deprecated resources clearly flagged** (e.g., `REDIS_HOST`), and always use real SSM paths/values for onboarding and debugging.

---

