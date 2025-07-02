resource "aws_cognito_user_pool" "main" {
  name = "User pool - z-j4by"

  lifecycle {
    prevent_destroy = true
    ignore_changes  = all   # ← one-liner, Terraform never diffs any fields
  }
}

resource "aws_cognito_user_pool_client" "gui" {
  name         = "tl-fif-desktop"
  user_pool_id = aws_cognito_user_pool.main.id

  lifecycle {
    prevent_destroy = true
    ignore_changes  = all
  }
}
