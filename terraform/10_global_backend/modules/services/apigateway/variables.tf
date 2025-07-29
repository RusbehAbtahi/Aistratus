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

variable "cognito_user_pool_id" {
  type = string
}

variable "cognito_client_id" {
  type = string
}
