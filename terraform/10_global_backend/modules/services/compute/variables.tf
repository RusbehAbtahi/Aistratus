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