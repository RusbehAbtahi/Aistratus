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