terraform {
  required_version = ">= 1.6"
}

provider "aws" {
  region = "eu-central-1"
}

locals {
  project = "tinyllama"
}

resource "aws_s3_bucket" "remote_state" {
  bucket = "tinnyllama-terraform-state"
  force_destroy = false

  versioning { enabled = true }
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
  tags = {
    Project = local.project
    Stage   = "bootstrap"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.remote_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "locks" {
  name         = "terraform_locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Project = local.project
    Stage   = "bootstrap"
  }
}

output "state_bucket" { value = aws_s3_bucket.remote_state.id }
output "lock_table"   { value = aws_dynamodb_table.locks.name }