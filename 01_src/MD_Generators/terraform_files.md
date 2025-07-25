# All Terraform Files and Corresponding Data

## terraform\10_global_backend\main.tf

```hcl
###############################################################################
# 10_global_backend / main.tf – definitive root configuration (LAM-001)      #
###############################################################################

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0.0"
    }
  }
}

provider "aws" {
  region = "eu-central-1"
}

################################################################################
# Core infrastructure                                                          #
################################################################################

module "networking" {
  source        = "./modules/core/networking"
  vpc_cidr      = "10.20.0.0/22"
  enable_nat_gw = false
}

module "auth" {
  source = "./modules/core/auth"
}

module "ssm_params" {
  source        = "./modules/core/ssm_params"
  env           = var.env
  ids           = local.ids
  global_values = local.global_ids
}

################################################################################
# Services                                                                     #
################################################################################

module "lambda_layers" {
  source          = "./modules/services/lambda_layers"
  env             = var.env
  artifact_bucket = var.artifact_bucket
  shared_deps_layer_s3_key = var.shared_deps_layer_s3_key
  layer_bucket              = var.layer_bucket  
}

module "iam_router" {
  source = "./modules/services/iam_router"
  env    = var.env
}

module "compute" {
  source          = "./modules/services/compute"
  env             = var.env
  artifact_bucket = var.artifact_bucket
  router_memory   = var.router_memory
  router_timeout  = var.router_timeout
  aws_region      = var.aws_region
  shared_deps_layer_arn = module.lambda_layers.arn
  depends_on = [module.ssm_params]
}


################################################################################
# Observability                                                                #
################################################################################

module "monitoring" {
  source               = "./modules/observability/monitoring"
  router_function_name = module.compute.router_function_name
  log_group_name       = module.compute.log_group_name
}

# ──────────────────────────────────────────────────────────────
# Resolve the Lambda *invoke ARN* once, so API Gateway receives
# a fully-qualified arn:aws:lambda:…:function/<name>:<version>/invocations
# ──────────────────────────────────────────────────────────────
#data "aws_lambda_function" "router" {
#  function_name = module.compute.router_function_name   # <- already output by compute module
#}


module "apigateway" {
  source              = "./modules/services/apigateway"
  env                 = var.env
  aws_region          = var.aws_region
  router_lambda_arn  = module.compute.router_invoke_arn
  router_lambda_name  = module.compute.router_function_name
}
```

## terraform\10_global_backend\outputs.tf

```hcl
locals {
  global_ids = {
    cognito_user_pool_id = module.auth.cognito_user_pool_id
    cognito_client_id    = module.auth.cognito_client_id
    cognito_domain       = module.auth.cognito_domain
    vpc_id               = module.networking.vpc_id
    public_subnet_ids    = jsonencode(module.networking.public_subnet_ids)
    private_subnet_ids   = jsonencode(module.networking.private_subnet_ids)
    router_api_url       = module.apigateway.api_endpoint
  }
}

# (keep the output block if you like, but the module call above now
#  reads from local.global_ids, which is always in scope)
output "global_ids" {
  value = local.global_ids
}
```

## terraform\10_global_backend\variables.tf

```hcl
variable "env" {
  type = string
}

variable "artifact_bucket" {
  type = string
}

variable "router_memory" {
  type    = number
  default = 512
}

variable "router_timeout" {
  type    = number
  default = 30
}

variable "aws_region" {
  description = "AWS region (must match provider region)"
  type        = string
  default     = "eu-central-1"
}

variable "shared_deps_layer_s3_key" {
  description = "S3 key for the Lambda layer ZIP"
  type        = string
}
variable "layer_bucket" {
  description = "S3 bucket that stores Lambda layer ZIPs"
  type        = string
}
```

## terraform\10_global_backend\backend.auto.tfvars

```hcl
bucket = "tinyllama-terraform-state"
key    = "global/terraform.tfstate"
region = "eu-central-1"
shared_deps_layer_s3_key = "layers/shared_deps_20250722-163252.zip"
layer_bucket = "lambda-layer-zip-108782059508"
```

## terraform\10_global_backend\backend.tf

```hcl
terraform {
  backend "s3" {
    bucket         = "tinnyllama-terraform-state"
    key            = "global/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "terraform_locks"
    encrypt        = true
  }
}
```

## terraform\10_global_backend\ci_role.tf

```hcl
###############################################
# GitHub Actions OIDC deploy role
###############################################

# 1️⃣  OIDC provider for github.com (one-time, re-usable)
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"] # GitHub OIDC CA thumbprint
}

# 2️⃣  IAM role assumed by GitHub Actions in *this* repo only
resource "aws_iam_role" "github_actions_deployer" {
  name = "tlfif-github-actions-deployer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:RusbehAbtahi/Aistratus:*"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

# 3️⃣  Inline policy – **read-only SSM + TF state bucket access**
resource "aws_iam_role_policy" "github_actions_deployer_policy" {
  role   = aws_iam_role.github_actions_deployer.id
  policy = file("${path.module}/updated-policy.json")
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions_deployer.arn
  description = "IAM role that the GitHub Actions workflow assumes."
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
```

## terraform\10_global_backend\locals_ids.tf

```hcl
locals {
  # Prefix becomes /tinyllama/default/*  or  /tinyllama/dev/* …
  ssm_prefix = "/tinyllama/${var.env}"

  ids = {
    cognito_user_pool_id = "${local.ssm_prefix}/cognito_user_pool_id"
    cognito_client_id    = "${local.ssm_prefix}/cognito_client_id"
    cognito_domain       = "${local.ssm_prefix}/cognito_domain"
    vpc_id               = "${local.ssm_prefix}/vpc_id"
    public_subnet_ids    = "${local.ssm_prefix}/public_subnet_ids"
    private_subnet_ids   = "${local.ssm_prefix}/private_subnet_ids"
    router_api_url       = "${local.ssm_prefix}/router_api_url"
  }
}
```

## terraform\10_global_backend\modules\core\auth\main.tf

```hcl
resource "aws_cognito_user_pool" "main" {
  name = "User pool - z-j4by"
  deletion_protection = "INACTIVE" 

# lifecycle {
#   prevent_destroy = true
#   ignore_changes  = all
# }

}

resource "aws_cognito_user_pool_client" "gui" {
  name         = "tl-fif-desktop"
  user_pool_id = aws_cognito_user_pool.main.id

#  lifecycle {
#    prevent_destroy = true
#    ignore_changes  = all
#  }
}

output "cognito_user_pool_id"  { value = aws_cognito_user_pool.main.id }
output "cognito_client_id"     { value = aws_cognito_user_pool_client.gui.id }
output "cognito_domain"        { value = aws_cognito_user_pool.main.endpoint }
```

## terraform\10_global_backend\modules\core\networking\main.tf

```hcl
########################################
# variables
########################################
variable "vpc_cidr"      { default = "10.20.0.0/22" }
variable "project"       { default = "tinyllama"    }
variable "enable_nat_gw" { default = true          }  # ← flip to true when you need egress

########################################
# data
########################################
data "aws_availability_zones" "azs" {}

########################################
# VPC
########################################
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name    = "${var.project}-vpc"
    Project = var.project
  }
}

########################################
# Subnets (1 public, 2 private)
########################################
locals {
  az = data.aws_availability_zones.azs.names[0]
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.20.0.0/24"
  availability_zone       = local.az
  map_public_ip_on_launch = true
  tags = { Name = "${var.project}-public-a" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = "10.20.1.0/24"
  availability_zone = local.az
  tags = { Name = "${var.project}-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = "10.20.2.0/24"
  availability_zone = local.az
  tags = { Name = "${var.project}-private-b" }
}

########################################
# IGW + optional NAT
########################################
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.project}-igw" }
}

resource "aws_eip" "nat" {
  count  = var.enable_nat_gw ? 1 : 0
  domain = "vpc"
  tags   = { Name = "${var.project}-nat-eip" }
}

resource "aws_nat_gateway" "natgw" {
  count         = var.enable_nat_gw ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public_a.id
  tags          = { Name = "${var.project}-natgw" }
}

########################################
# Route tables
########################################
# public RT
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = { Name = "${var.project}-public-rt" }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

# private RT
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.project}-private-rt" }
}

# default route in private RT (only if NAT-GW exists)
resource "aws_route" "private_default" {
  count                  = var.enable_nat_gw ? 1 : 0
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.natgw[0].id
}

resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}

output "vpc_id"             { value = aws_vpc.this.id }
output "public_subnet_ids"  { value = [aws_subnet.public_a.id] }
output "private_subnet_ids" { value = [aws_subnet.private_a.id, aws_subnet.private_b.id] }
```

## terraform\10_global_backend\modules\core\ssm_params\main.tf

```hcl
# WHY
#   Writer: pushes the collected IDs into SSM for *this* env only.
# WHERE
#   New directory 10_global_backend/modules/ssm_params
# HOW
#   Called from main.tf (next snippet).

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

########################
#  WRITE
########################
resource "aws_ssm_parameter" "global_ids" {
  for_each = var.ids
  name     = each.value
  type     = "String"
  value    = var.global_values[each.key]
  overwrite = true            # <-- idempotent re-apply
  tags = {
    Project = "tinyllama"
    Env     = var.env
    Scope   = "global-id"
  }
}

########################
#  VARIABLES
########################
variable "ids" {
  type        = map(string)
  description = "SSM names from locals"
}

variable "global_values" {
  type        = map(string)
  description = "Actual IDs coming from root outputs"
}

variable "env" {
  type        = string
  description = "Same as var.env at root"
}
```

## terraform\10_global_backend\modules\observability\monitoring\main.tf

```hcl
#############################################################
# CloudWatch metrics & alarms for TinyLlama Router Lambda   #
#############################################################

/* ----------------
   Module variables
   ---------------- */
variable "router_function_name" {
  description = "Exact name of the Router Lambda function"
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch log-group name for the Router Lambda"
  type        = string
}

/* ------------------------------
   Metric filter: count 4xx errors
   ------------------------------ */
resource "aws_cloudwatch_log_metric_filter" "error_4xx" {
  name           = "${var.router_function_name}-4xx"
  log_group_name = var.log_group_name
  pattern        = "{$.statusCode = 4*}"

  metric_transformation {
    name      = "Router4xx"
    namespace = "TLFIF/LAM"
    value     = "1"
  }
}

/* --------------------------------
   Alarm: p95 latency > 60 ms (3 min)
   -------------------------------- */
resource "aws_cloudwatch_metric_alarm" "p95_latency" {
  alarm_name          = "${var.router_function_name}-p95-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  extended_statistic           = "p95"
  threshold           = 60
  datapoints_to_alarm = 3
  dimensions = {
    FunctionName = var.router_function_name
  }
  alarm_description = "Router Lambda p95 latency > 60 ms for 3 consecutive minutes"
}

/* -------
   Outputs
   ------- */
output "alarm_name" {
  description = "Name of the p95 latency CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.p95_latency.alarm_name
}
```

## terraform\10_global_backend\modules\services\apigateway\main.tf

```hcl
########################################
#  HTTP API  (tlfif-<env>-router-api)  #
########################################
resource "aws_apigatewayv2_api" "router" {
  name          = "tlfif-${var.env}-router-api"
  protocol_type = "HTTP"
}

########################################
#  Lambda → API Integration (proxy)    #
########################################
resource "aws_apigatewayv2_integration" "lambda_proxy" {
  api_id                 = aws_apigatewayv2_api.router.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.router_lambda_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

########################################
#  Routes                              #
########################################
resource "aws_apigatewayv2_route" "ping" {
  api_id    = aws_apigatewayv2_api.router.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy.id}"
}

resource "aws_apigatewayv2_route" "infer" {
  api_id    = aws_apigatewayv2_api.router.id
  route_key = "POST /infer"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy.id}"
}

resource "aws_apigatewayv2_route" "stop" {
  api_id    = aws_apigatewayv2_api.router.id
  route_key = "POST /stop"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy.id}"
}

########################################
#  $default Stage (auto-deploy)        #
########################################
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.router.id
  name        = "$default"
  auto_deploy = true
}

########################################
#  Lambda permission (invoke)          #
########################################
resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowAPIGatewayInvoke-${var.env}"
  action        = "lambda:InvokeFunction"
  function_name = var.router_lambda_name
  qualifier     = "prod"
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.router.execution_arn}/*/*"
}

########################################
#  SSM parameter with endpoint         #
########################################
resource "aws_ssm_parameter" "endpoint_url" {
  name  = "/tinyllama/${var.env}/router_api_url"
  type  = "String"
  value = aws_apigatewayv2_api.router.api_endpoint
  overwrite = true
  tags = {
    Project = "tinyllama"
    Env     = var.env
    Scope   = "api-endpoint"
  }
}

```

## terraform\10_global_backend\modules\services\apigateway\outputs.tf

```hcl
output "api_id"       { value = aws_apigatewayv2_api.router.id }
output "api_endpoint" { value = aws_apigatewayv2_api.router.api_endpoint }
output "ssm_param"    { value = aws_ssm_parameter.endpoint_url.name }
```

## terraform\10_global_backend\modules\services\apigateway\variables.tf

```hcl
variable "env" {
  description = "Terraform workspace / environment (e.g. default, dev)"
  type        = string
}

variable "router_lambda_arn" {
  description = "ARN of the Router Lambda function (alias prod)"
  type        = string
}

variable "router_lambda_name" {
  description = "Name of the Router Lambda function"
  type        = string
}

variable "aws_region" {
  description = "Region (must match provider)"
  type        = string
}
```

## terraform\10_global_backend\modules\services\compute\main.tf

```hcl

module "iam" {
  source = "../iam_router"
  env    = var.env
}

data "aws_ssm_parameter" "pool"   { name = "/tinyllama/${var.env}/cognito_user_pool_id" }
data "aws_ssm_parameter" "client" { name = "/tinyllama/${var.env}/cognito_client_id" }

resource "aws_lambda_function" "router" {
  function_name = "tlfif-${var.env}-router"
  filename      = "${path.module}/../../../../../router.zip"
  source_code_hash  = filebase64sha256("${path.module}/../../../../../router.zip")
  publish           = true
  handler       = "tinyllama.router.handler.lambda_handler"
  runtime       = "python3.12"
  role          = module.iam.arn
  layers        = [var.shared_deps_layer_arn]
  memory_size   = var.router_memory
  timeout       = var.router_timeout
  tracing_config { mode = "Active" }
  environment {
    variables = {
      TL_DISABLE_LAM_ROUTER = "0"
      COGNITO_ISSUER = "https://cognito-idp.${var.aws_region}.amazonaws.com/${data.aws_ssm_parameter.pool.value}"
      COGNITO_AUD    = data.aws_ssm_parameter.client.value
    }
  }
}

resource "aws_lambda_alias" "prod" {
  name             = "prod"
  function_name    = aws_lambda_function.router.function_name
  function_version = aws_lambda_function.router.publish ? aws_lambda_function.router.version : "$LATEST"
  lifecycle { create_before_destroy = true }
}

resource "aws_cloudwatch_log_group" "router" {
  name              = "/aws/lambda/${aws_lambda_function.router.function_name}"
  retention_in_days = 30
}
```

## terraform\10_global_backend\modules\services\compute\outputs.tf

```hcl
output "router_function_name" {
  description = "Name of the deployed Router Lambda function"
  value       = aws_lambda_function.router.function_name
}

output "log_group_name" {
  description = "CloudWatch Log Group name for the Router Lambda"
  value       = aws_cloudwatch_log_group.router.name
}

output "router_invoke_arn" {
  description = "Invoke ARN for the prod alias of the router Lambda"
  value       = aws_lambda_alias.prod.invoke_arn
}
```

## terraform\10_global_backend\modules\services\compute\variables.tf

```hcl
variable "env" {
  description = "Terraform workspace / environment (e.g. dev, prod)"
  type        = string
}

variable "artifact_bucket" {
  description = "S3 bucket that stores Lambda layer artefacts"
  type        = string
}

variable "router_memory" {
  description = "Lambda memory (MB)"
  type        = number
  default     = 512
}

variable "router_timeout" {
  description = "Lambda timeout (seconds)"
  type        = number
  default     = 30
}

variable "aws_region" {
  description = "AWS region for constructing Cognito issuer URL"
  type        = string
}

variable "shared_deps_layer_arn" {
  description = "ARN for the shared Lambda Layer"
  type        = string
}
```

## terraform\10_global_backend\modules\services\iam_router\main.tf

```hcl
# IAM execution role for TinyLlama Router
# workspace-safe: name carries ${var.env}

variable "env" {
  description = "Terraform workspace / environment (e.g. default, dev)"
  type        = string
}

# Assume-role policy for Lambda
data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "router" {
  name               = "tlfif-${var.env}-router"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
  lifecycle {
    create_before_destroy = true
  }
}

# AWS-managed basic execution (logs/X-Ray)
resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.router.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Inline policy: read only the TinyLlama parameter subtree
data "aws_iam_policy_document" "ssm_read" {
  statement {
    sid       = "TLFIFReadSSM"
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParameterHistory"]
    resources = ["arn:aws:ssm:*:*:parameter/tinyllama/*"]
  }
}

resource "aws_iam_role_policy" "ssm" {
  name   = "tlfif-${var.env}-ssm-read"
  role   = aws_iam_role.router.id
  policy = data.aws_iam_policy_document.ssm_read.json
}

# Output ARN for compute module
output "arn" {
  description = "IAM role ARN for Router Lambda"
  value       = aws_iam_role.router.arn
}
```

## terraform\10_global_backend\modules\services\lambda_layers\main.tf

```hcl
variable "env" {}
variable "artifact_bucket" {}

locals { layer_name = "tlfif-${var.env}-shared-deps" }


resource "aws_lambda_layer_version" "this" {
  layer_name          = local.layer_name
  s3_bucket           = var.layer_bucket
  s3_key = var.shared_deps_layer_s3_key
  compatible_runtimes = ["python3.12"]
  description         = "TinyLlama shared deps"
  lifecycle { create_before_destroy = true }
}

output "arn" { value = aws_lambda_layer_version.this.arn }
```

## terraform\10_global_backend\modules\services\lambda_layers\variables.tf

```hcl
variable "shared_deps_layer_s3_key" {
  description = "S3 key for the Lambda layer ZIP"
  type        = string
}
variable "layer_bucket" {
  description = "S3 bucket that holds timestamped layer zips"
  type        = string
}
```

## terraform\10_global_backend\allow-delete-route.json

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowManageHTTPAPI",
      "Effect": "Allow",
      "Action": [
        "apigatewayv2:GetApis",
        "apigatewayv2:GetRoutes",
        "apigatewayv2:DeleteRoute",
        "apigatewayv2:UpdateStage"
      ],
      "Resource": "arn:aws:apigateway:eu-central-1::/apis/exubbfn15f/*"
    }
  ]
}
```

## terraform\10_global_backend\allow-manage-router.json

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowManageRouterAPI",
      "Effect": "Allow",
      "Action": [
        "apigatewayv2:GetRoutes",
        "apigatewayv2:DeleteRoute",
        "apigatewayv2:UpdateStage"
      ],
      "Resource": [
        "arn:aws:apigateway:eu-central-1::/apis/exubbfn15f/routes/*",
        "arn:aws:apigateway:eu-central-1::/apis/exubbfn15f/stages/$default"
      ]
    }
  ]
}
```

## terraform\10_global_backend\updated-policy.json

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SSMList",
      "Effect": "Allow",
      "Action": [
        "ssm:DescribeParameters",
        "ssm:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SSMGet",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParameterHistory",
        "ssm:ListTagsForResource"
      ],
      "Resource": "arn:aws:ssm:eu-central-1:108782059508:parameter/*"
    },
    {
      "Sid": "IAMInspection",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": [
        "arn:aws:iam::108782059508:role/tlfif-default-router",
        "arn:aws:iam::108782059508:role/tlfif-github-actions-deployer"
      ]
    },
    {
      "Sid": "S3StateBackend",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::tinnyllama-terraform-state"
    },
    {
      "Sid": "S3StateBackendObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::tinnyllama-terraform-state/*"
    },
    {
      "Sid": "ArtifactBucketList",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::tinyllama-data-108782059508"
    },
    {
      "Sid": "ArtifactBucketObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::tinyllama-data-108782059508/layers/*"
    },
    {
      "Sid": "ArtifactBucketTagging",
      "Effect": "Allow",
      "Action": [
        "s3:GetObjectTagging"
      ],
      "Resource": "arn:aws:s3:::tinyllama-data-108782059508/layers/*"
    },
    {
      "Sid": "DynamoDBLocks",
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:eu-central-1:108782059508:table/terraform_locks"
    },
    {
      "Sid": "OIDCProvider",
      "Effect": "Allow",
      "Action": [
        "iam:GetOpenIDConnectProvider"
      ],
      "Resource": "arn:aws:iam::108782059508:oidc-provider/token.actions.githubusercontent.com"
    },
    {
      "Sid": "CognitoRead",
      "Effect": "Allow",
      "Action": [
        "cognito-idp:DescribeUserPool",
        "cognito-idp:GetUserPoolMfaConfig",
        "cognito-idp:DescribeUserPoolClient"
      ],
      "Resource": "arn:aws:cognito-idp:eu-central-1:108782059508:userpool/*"
    },
    {
      "Sid": "EC2Read",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeVpcs",
        "ec2:DescribeVpcAttribute",
        "ec2:DescribeSubnets",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeRouteTables"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LambdaGetLayerVersion",
      "Effect": "Allow",
      "Action": [
        "lambda:GetLayerVersion"
      ],
      "Resource": [
        "arn:aws:lambda:eu-central-1:108782059508:layer:tlfif-default-shared-deps:*"
      ]
    },
    {
      "Sid": "LambdaGetFunction",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunction"
      ],
      "Resource": [
        "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
      ]
    },
    {
      "Sid": "LambdaListVersions",
      "Effect": "Allow",
      "Action": [
        "lambda:ListVersionsByFunction"
      ],
      "Resource": [
        "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
      ]
    },
    {
      "Sid": "LambdaGetFunctionCodeSigningConfig",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunctionCodeSigningConfig"
      ],
      "Resource": [
        "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
      ]
    },
    {
      "Sid": "CloudWatchDescribeAlarms",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms"
      ],
      "Resource": "arn:aws:cloudwatch:eu-central-1:108782059508:alarm:*"
    },
    {
      "Sid": "LambdaGetAlias",
      "Effect": "Allow",
      "Action": [
        "lambda:GetAlias"
      ],
      "Resource": "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
    },
    {
      "Sid": "LogsDescribeLogGroups",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups"
      ],
      "Resource": "*"
    },
    {
       "Sid": "CloudWatchListTagsForResource",
       "Effect": "Allow",
       "Action": [
       "cloudwatch:ListTagsForResource"
     ],
       "Resource": "arn:aws:cloudwatch:eu-central-1:108782059508:alarm:*"
   },
   {
       "Sid": "LogsListTagsForResource",
       "Effect": "Allow",
       "Action": [
       "logs:ListTagsForResource"
      ],
       "Resource": "*"
   },
   {
        "Sid": "LogsDescribeMetricFilters",
        "Effect": "Allow",
         "Action": [
        "logs:DescribeMetricFilters"
      ],
         "Resource": "*"
  },

  {
        "Sid": "CognitoDescribeUserPool",
        "Effect": "Allow",
        "Action": [
        "cognito-idp:DescribeUserPool"
     ],
         "Resource": "arn:aws:cognito-idp:eu-central-1:108782059508:userpool/*"
  },
  {
        "Sid": "ApiGatewayGetApi",
        "Effect": "Allow",
        "Action": [
        "apigateway:GET"
     ],
        "Resource": "arn:aws:apigateway:eu-central-1::/apis/*"
   },
   {
        "Sid": "LambdaGetPolicyWildcard",
        "Effect": "Allow",
        "Action": [
        "lambda:GetPolicy"
      ],
        "Resource": "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router:*"
    },
    {
        "Sid": "IamPutRolePolicy",
        "Effect": "Allow",
        "Action": [
        "iam:PutRolePolicy"
     ],
        "Resource": "arn:aws:iam::108782059508:role/tlfif-github-actions-deployer"
  },
  {
         "Sid": "SsmAddTagsToResource",
         "Effect": "Allow",
          "Action": [
           "ssm:AddTagsToResource"
      ],
          "Resource": "arn:aws:ssm:eu-central-1:108782059508:parameter/tinyllama/default/router_api_url"
  },
  {
           "Sid": "ApiGatewayPatchStage",
            "Effect": "Allow",
             "Action": [
            "apigateway:PATCH"
     ],
            "Resource": "arn:aws:apigateway:eu-central-1::/apis/rjg3dvt5el/stages/$default"
   },

   {
            "Sid": "LogsCreateLogDelivery",
            "Effect": "Allow",
            "Action": [
            "logs:CreateLogDelivery"
     ],
             "Resource": "*"
   }, 
   {
            "Sid": "LambdaUpdateFunctionCode",
            "Effect": "Allow",
            "Action": [
            "lambda:UpdateFunctionCode"
     ],
           "Resource": "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
   },

  {
             "Sid": "LogsListLogDeliveries",
             "Effect": "Allow",
             "Action": [
             "logs:ListLogDeliveries"
         ],
             "Resource": "*"
  },
  {
             "Sid": "LambdaPublishVersion",
             "Effect": "Allow",
             "Action": [
             "lambda:PublishVersion"
         ],
              "Resource": "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
    },
    {
              "Sid": "LogsGetLogDelivery",
               "Effect": "Allow",
               "Action": [
               "logs:GetLogDelivery"
       ],
              "Resource": "*"
    },
   {
              "Sid": "LambdaGetFunctionConfiguration",
              "Effect": "Allow",
              "Action": [
              "lambda:GetFunctionConfiguration"
     ],
              "Resource": "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router:*"
   },
   {
             "Sid": "LogsUpdateLogDelivery",
             "Effect": "Allow",
             "Action": [
            "logs:UpdateLogDelivery"
     ],
             "Resource": "*"
   }, 
   {
            "Sid": "LambdaUpdateAlias",
            "Effect": "Allow",
            "Action": [
             "lambda:UpdateAlias"
     ],
              "Resource": "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
     },
    {
             "Sid": "S3MultipartUploads",
             "Effect": "Allow",
             "Action": [
             "s3:CreateMultipartUpload",
             "s3:ListMultipartUploadParts",
             "s3:CompleteMultipartUpload",
             "s3:AbortMultipartUpload"
       ],
             "Resource": "arn:aws:s3:::tinyllama-data-108782059508/layers/*"
     },
     {
             "Sid": "LambdaAddRemovePermission",
              "Effect": "Allow",
              "Action": [
              "lambda:AddPermission",
              "lambda:RemovePermission"
    ],
              "Resource": "arn:aws:lambda:eu-central-1:108782059508:function:tlfif-default-router"
}






  ]
}
```
