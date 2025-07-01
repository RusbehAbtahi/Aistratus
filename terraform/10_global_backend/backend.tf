terraform {
  backend "s3" {
    bucket         = "tinnyllama-terraform-state"
    key            = "global/terraform.tfstate"
    region         = "eu-central-1"
    dynamodb_table = "terraform_locks"
    encrypt        = true
  }
}