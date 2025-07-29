# IAM execution role for TinyLlama Router
# workspace-safe: name carries ${var.env}

variable "env" {
  description = "Terraform workspace / environment (e.g. default, dev)"
  type        = string
}

# Assume-role policy for Lambda
data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "router" {
  name               = "tlfif-${var.env}-router"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
  lifecycle {
    create_before_destroy = true
  }
}

# AWS-managed basic execution (logs/X-Ray)
resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.router.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Inline policy: read only the TinyLlama parameter subtree
data "aws_iam_policy_document" "ssm_read" {
  statement {
    sid       = "TLFIFReadSSM"
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParameterHistory"]
    resources = ["arn:aws:ssm:*:*:parameter/tinyllama/*"]
  }
}

resource "aws_iam_role_policy" "ssm" {
  name   = "tlfif-${var.env}-ssm-read"
  role   = aws_iam_role.router.id
  policy = data.aws_iam_policy_document.ssm_read.json
}

# Output ARN for compute module
output "arn" {
  description = "IAM role ARN for Router Lambda"
  value       = aws_iam_role.router.arn
}

###############################################################################
# SQS  ·  allow Lambda to enqueue jobs (SendMessage to the single job queue)
###############################################################################

# 1. Resolve the real queue ARN from SSM
data "aws_ssm_parameter" "job_queue_arn" {
  name = "/tinyllama/${var.env}/job_queue_arn"
}

# 2. Minimal, least-privilege policy
data "aws_iam_policy_document" "sqs_send" {
  statement {
    sid       = "TLFIFSendSQS"
    actions   = ["sqs:SendMessage"]
    resources = [data.aws_ssm_parameter.job_queue_arn.value]
  }
}

resource "aws_iam_role_policy" "sqs_send" {
  role   = aws_iam_role.router.id
  policy = data.aws_iam_policy_document.sqs_send.json
}
