#!/usr/bin/env bash
set -euo pipefail

LAMBDA_NAME="tinyllama-router"
SRC_DIR="01_src/tinyllama/orchestration/lambda_router"
ZIP_OUT="build/router.zip"

mkdir -p build
rm -f "$ZIP_OUT"

# ---------- package ---------------------------------------------------------
if command -v zip >/dev/null 2>&1; then
  (cd "$SRC_DIR" && zip -r "../../../../$ZIP_OUT" .)
else
  # Windows: fall back to PowerShell’s Compress-Archive
  powershell.exe -NoProfile -Command \
    "Compress-Archive -Path '$SRC_DIR/*' -DestinationPath '$ZIP_OUT' -Force"
fi

# ---------- deploy ----------------------------------------------------------
if aws lambda get-function --function-name "$LAMBDA_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$LAMBDA_NAME" \
                                  --zip-file "fileb://$ZIP_OUT"
else
  ROLE_ARN=$(aws iam get-role --role-name tinyllama-lambda-role \
                              --query 'Role.Arn' --output text)
  aws lambda create-function --function-name "$LAMBDA_NAME" \
                             --runtime python3.12 \
                             --handler handler.lambda_handler \
                             --role "$ROLE_ARN" \
                             --zip-file "fileb://$ZIP_OUT"
fi
