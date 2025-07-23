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