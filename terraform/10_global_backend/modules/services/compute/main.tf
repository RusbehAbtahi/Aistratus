
module "iam" {
  source = "../iam_router"
  env    = var.env
}

data "aws_ssm_parameter" "pool"   { name = "/tinyllama/${var.env}/cognito_user_pool_id" }
data "aws_ssm_parameter" "client" { name = "/tinyllama/${var.env}/cognito_client_id" }

resource "aws_lambda_function" "router" {
  function_name = "tlfif-${var.env}-router"
  filename      = "${path.module}/../../../../../router.zip"
  source_code_hash  = filebase64sha256("${path.module}/../../../../../router.zip")
  publish           = true
  handler       = "tinyllama.router.handler.lambda_handler"
  runtime       = "python3.12"
  role          = module.iam.arn
  layers        = [var.shared_deps_layer_arn]
  memory_size   = var.router_memory
  timeout       = var.router_timeout
  tracing_config { mode = "Active" }
  environment {
    variables = {
      TL_DISABLE_LAM_ROUTER = "0"
      COGNITO_ISSUER = "https://cognito-idp.${var.aws_region}.amazonaws.com/${data.aws_ssm_parameter.pool.value}"
      COGNITO_AUD    = data.aws_ssm_parameter.client.value
    }
  }
}

resource "aws_lambda_alias" "prod" {
  name             = "prod"
  function_name    = aws_lambda_function.router.function_name
  function_version = aws_lambda_function.router.publish ? aws_lambda_function.router.version : "$LATEST"
  lifecycle { create_before_destroy = true }
}

resource "aws_cloudwatch_log_group" "router" {
  name              = "/aws/lambda/${aws_lambda_function.router.function_name}"
  retention_in_days = 30
}