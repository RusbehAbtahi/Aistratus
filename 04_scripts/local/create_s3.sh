#!/usr/bin/env bash
acc=$(aws sts get-caller-identity --query Account --output text)
bucket="tinyllama-data-${acc}"
aws s3api create-bucket \
  --bucket "$bucket" \
  --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1
aws s3api put-bucket-versioning \
  --bucket "$bucket" \
  --versioning-configuration Status=Enabled
echo "DATA_BUCKET=$bucket" >> .env