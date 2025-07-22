variable "shared_deps_layer_s3_key" {
  description = "S3 key for the Lambda layer ZIP"
  type        = string
}
variable "layer_bucket" {
  description = "S3 bucket that holds timestamped layer zips"
  type        = string
}