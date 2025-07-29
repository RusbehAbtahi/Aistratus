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
  cognito_user_pool_id = module.auth.cognito_user_pool_id
  cognito_client_id    = module.auth.cognito_client_id


}

module "sqs" {
  source = "./modules/services/sqs"
  env    = var.env
}
