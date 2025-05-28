#!/usr/bin/env bash
# 1. Create the Lambda role using our trust policy
aws iam create-role \
  --role-name tinyllama-lambda-role \
  --assume-role-policy-document file://00_infra/lambda_trust_policy.json \
  --description "Executes tinyllama router"

# 2. Attach AWS-managed execution policy
aws iam attach-role-policy \
  --role-name tinyllama-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 3. Add inline policy for S3 + Secrets
aws iam put-role-policy \
  --role-name tinyllama-lambda-role \
  --policy-name tinyllama-s3-secrets \
  --policy-document file://00_infra/lambda_inline_policy.json
