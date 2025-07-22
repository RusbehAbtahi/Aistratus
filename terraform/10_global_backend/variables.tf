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
