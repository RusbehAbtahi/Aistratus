variable "env" {}
variable "artifact_bucket" {}

locals { layer_name = "tlfif-${var.env}-shared-deps" }

resource "aws_s3_object" "pkg" {
  bucket = var.artifact_bucket
  key    = "layers/${local.layer_name}.zip"
  source = "${path.module}/../../../../../01_src/lambda_layers/shared_deps/shared_deps.zip"
  etag   = filemd5("${path.module}/../../../../../01_src/lambda_layers/shared_deps/shared_deps.zip")
}



resource "aws_lambda_layer_version" "this" {
  layer_name          = local.layer_name
  s3_bucket           = var.artifact_bucket
  s3_key              = aws_s3_object.pkg.key
  compatible_runtimes = ["python3.12"]
  description         = "TinyLlama shared deps"
  lifecycle { create_before_destroy = true }
}

output "arn" { value = aws_lambda_layer_version.this.arn }