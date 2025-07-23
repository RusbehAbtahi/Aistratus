locals {
  # Prefix becomes /tinyllama/default/*  or  /tinyllama/dev/* …
  ssm_prefix = "/tinyllama/${var.env}"

  ids = {
    cognito_user_pool_id = "${local.ssm_prefix}/cognito_user_pool_id"
    cognito_client_id    = "${local.ssm_prefix}/cognito_client_id"
    cognito_domain       = "${local.ssm_prefix}/cognito_domain"
    vpc_id               = "${local.ssm_prefix}/vpc_id"
    public_subnet_ids    = "${local.ssm_prefix}/public_subnet_ids"
    private_subnet_ids   = "${local.ssm_prefix}/private_subnet_ids"
    router_api_url       = "${local.ssm_prefix}/router_api_url"
  }
}