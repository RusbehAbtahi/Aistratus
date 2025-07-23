output "api_id"       { value = aws_apigatewayv2_api.router.id }
output "api_endpoint" { value = aws_apigatewayv2_api.router.api_endpoint }
output "ssm_param"    { value = aws_ssm_parameter.endpoint_url.name }