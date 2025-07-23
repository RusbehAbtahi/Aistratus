resource "aws_cognito_user_pool" "main" {
  name = "User pool - z-j4by"
  deletion_protection = "INACTIVE" 

# lifecycle {
#   prevent_destroy = true
#   ignore_changes  = all
# }

}

resource "aws_cognito_user_pool_client" "gui" {
  name         = "tl-fif-desktop"
  user_pool_id = aws_cognito_user_pool.main.id

#  lifecycle {
#    prevent_destroy = true
#    ignore_changes  = all
#  }
}

output "cognito_user_pool_id"  { value = aws_cognito_user_pool.main.id }
output "cognito_client_id"     { value = aws_cognito_user_pool_client.gui.id }
output "cognito_domain"        { value = aws_cognito_user_pool.main.endpoint }
