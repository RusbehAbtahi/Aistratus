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
}


################################################################################
# Observability                                                                #
################################################################################

module "monitoring" {
  source               = "./modules/observability/monitoring"
  router_function_name = module.compute.router_function_name
  log_group_name       = module.compute.log_group_name
}
