########################################
#  HTTP API  (tlfif-<env>-router-api)  #
########################################
resource "aws_apigatewayv2_api" "router" {
  name          = "tlfif-${var.env}-router-api"
  protocol_type = "HTTP"
}


resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.router.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  name = "cognito"
  jwt_configuration {
    audience = [var.cognito_client_id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${var.cognito_user_pool_id}"
  }
}

########################################
#  Lambda → API Integration (proxy)    #
########################################
resource "aws_apigatewayv2_integration" "lambda_proxy" {
  api_id                 = aws_apigatewayv2_api.router.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.router_lambda_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

########################################
#  Routes                              #
########################################
resource "aws_apigatewayv2_route" "ping" {
  api_id    = aws_apigatewayv2_api.router.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy.id}"
}

resource "aws_apigatewayv2_route" "infer" {
  api_id    = aws_apigatewayv2_api.router.id
  route_key = "POST /infer"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id

}

resource "aws_apigatewayv2_route" "stop" {
  api_id    = aws_apigatewayv2_api.router.id
  route_key = "POST /stop"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_proxy.id}"
}

########################################
#  $default Stage (auto-deploy)        #
########################################
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.router.id
  name        = "$default"
  auto_deploy = true
}

########################################
#  Lambda permission (invoke)          #
########################################
resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowAPIGatewayInvoke-${var.env}"
  action        = "lambda:InvokeFunction"
  function_name = var.router_lambda_name
  qualifier     = "prod"
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.router.execution_arn}/*/*"
}

########################################
#  SSM parameter with endpoint         #
########################################
resource "aws_ssm_parameter" "endpoint_url" {
  name  = "/tinyllama/${var.env}/router_api_url"
  type  = "String"
  value = aws_apigatewayv2_api.router.api_endpoint
  overwrite = true
  tags = {
    Project = "tinyllama"
    Env     = var.env
    Scope   = "api-endpoint"
  }
}

