resource "aws_cognito_user_pool" "main" {
  provider = aws
  name     = "tinyllama-user-pool"
}

resource "aws_cognito_user_pool_client" "gui" {
  provider = aws
  name         = "tinyllama-gui-client"
  user_pool_id = aws_cognito_user_pool.main.id
  generate_secret = false
}
