###############################################
# GitHub Actions OIDC deploy role
###############################################

# 1️⃣  OIDC provider for github.com (one-time, re-usable)
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"] # GitHub OIDC CA thumbprint
}

# 2️⃣  IAM role assumed by GitHub Actions in *this* repo only
resource "aws_iam_role" "github_actions_deployer" {
  name = "tlfif-github-actions-deployer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:RusbehAbtahi/Aistratus:*"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

# 3️⃣  Inline policy – **read-only SSM + TF state bucket access**
resource "aws_iam_role_policy" "github_actions_deployer_policy" {
  role = aws_iam_role.github_actions_deployer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # read SSM parameters written by modules/auth/ssm.tf
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParameterHistory"]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/tlfif/cognito/*"
      },
      # backend-state bucket read/write so CI can run terraform plan/apply
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::tlfif-terraform-state",
          "arn:aws:s3:::tlfif-terraform-state/*"
        ]
      },
      # allow locking via DynamoDB if you use it
      {
        Effect   = "Allow"
        Action   = ["dynamodb:*"]
        Resource = "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/terraform-lock"
      }
    ]
  })
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions_deployer.arn
  description = "IAM role that the GitHub Actions workflow assumes."
}
data "aws_caller_identity" "current" {}
data "aws_region"          "current" {}
