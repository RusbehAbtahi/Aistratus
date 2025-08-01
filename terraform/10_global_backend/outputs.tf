locals {
  global_ids = {
    cognito_user_pool_id = module.auth.cognito_user_pool_id
    cognito_client_id    = module.auth.cognito_client_id
    cognito_domain       = module.auth.cognito_domain
    vpc_id               = module.networking.vpc_id
    public_subnet_ids    = jsonencode(module.networking.public_subnet_ids)
    private_subnet_ids   = jsonencode(module.networking.private_subnet_ids)
    router_api_url       = module.apigateway.api_endpoint
    job_queue_url        = module.sqs.queue_url
    job_queue_arn        = module.sqs.queue_arn
  }
}

# (keep the output block if you like, but the module call above now
#  reads from local.global_ids, which is always in scope)
output "global_ids" {
  value = local.global_ids
}
