output "router_function_name" {
  description = "Name of the deployed Router Lambda function"
  value       = aws_lambda_function.router.function_name
}

output "log_group_name" {
  description = "CloudWatch Log Group name for the Router Lambda"
  value       = aws_cloudwatch_log_group.router.name
}

output "router_invoke_arn" {
  description = "Invoke ARN for the prod alias of the router Lambda"
  value       = aws_lambda_alias.prod.invoke_arn
}