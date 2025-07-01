###############################################
# 10_global_backend/main.tf
# — root configuration
###############################################

provider "aws" {
  region = "eu-central-1"
}

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0.0"   # stay on 6.0.x, do not upgrade to 6.1+
    }
  }
}

# ─────────────────────────────────────────────
# Modules
# ─────────────────────────────────────────────
module "networking" {
  source         = "./modules/networking"
  vpc_cidr       = "10.20.0.0/22"
  enable_nat_gw  = false         # ← this single line turns the NAT-GW ON
}


module "auth" {
  source = "./modules/auth"
}
