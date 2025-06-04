#!/usr/bin/env bash
set -euo pipefail

# Create a clean UTF-8 JSON payload file for Lambda
printf '%s' '{"body":"{\"prompt\":\"Hello, world!\"}"}' > payload.json

# Invoke the Lambda function using that payload
aws lambda invoke \
  --function-name tinyllama-router \
  --payload fileb://payload.json \
  /tmp/output.json

# Display the Lambda’s response
cat /tmp/output.json

# (Optional) clean up the payload file
rm -f payload.json
aws s3 cp s3://tinyllama-data-108782059508/inputs/d33cd051-2466-4a0d-9753-0411f9dc84dd.txt -