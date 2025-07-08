variable "env" {
  description = "Environment key used in SSM paths (default|dev|prod|…)"
  type        = string
  default     = "default"
}