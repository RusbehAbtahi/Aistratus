#!/usr/bin/env bash
set -euo pipefail

LAMBDA_NAME="tinyllama-router"
API_NAME="tinyllama-api"

# 1. Look up account ID and Lambda ARN
ACC=$(aws sts get-caller-identity --query Account --output text)
LAMBDA_ARN="arn:aws:lambda:eu-central-1:${ACC}:function:${LAMBDA_NAME}"

# 2. Create HTTP API
API_ID=$(aws apigatewayv2 create-api            --name "${API_NAME}"            --protocol-type HTTP            --target "${LAMBDA_ARN}"            --query ApiId --output text)

# 3. Grant API Gateway permission to invoke Lambda
aws lambda add-permission   --function-name "${LAMBDA_NAME}"   --statement-id "apigw-${API_ID}"   --action lambda:InvokeFunction   --principal apigateway.amazonaws.com   --source-arn "arn:aws:execute-api:eu-central-1:${ACC}:${API_ID}/*/*"

# 4. Persist API_ID to .env for later use
echo "API_ID=${API_ID}" >> .env
echo "Created API ${API_ID} and stored API_ID in .env"