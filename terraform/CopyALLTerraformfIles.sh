#!/usr/bin/env bash

# ──────────────────────────────────────
# Output file
# ──────────────────────────────────────
OUTPUT_FILE="all_tree_dump.txt"

# ──────────────────────────────────────
# Files list (exactly as per your tree)
# ──────────────────────────────────────
FILES=(
  "terraform/10_global_backend/terraform.tfstate"
  "terraform/10_global_backend/backend.auto.tfvars"
  "terraform/10_global_backend/backend.tf"
  "terraform/10_global_backend/ci_role.tf"
  "terraform/10_global_backend/locals_ids.tf"
  "terraform/10_global_backend/main.tf"
  "terraform/10_global_backend/modules/core/auth/main.tf"
  "terraform/10_global_backend/modules/core/networking/main.tf"
  "terraform/10_global_backend/modules/core/security/.gitkeep"
  "terraform/10_global_backend/modules/core/ssm_params/main.tf"
  "terraform/10_global_backend/modules/observability/monitoring/main.tf"
  "terraform/10_global_backend/modules/services/apigateway/main.tf"
  "terraform/10_global_backend/modules/services/apigateway/outputs.tf"
  "terraform/10_global_backend/modules/services/apigateway/variables.tf"
  "terraform/10_global_backend/modules/services/compute/main.tf"
  "terraform/10_global_backend/modules/services/compute/outputs.tf"
  "terraform/10_global_backend/modules/services/compute/variables.tf"
  "terraform/10_global_backend/modules/services/iam_router/main.tf"
  "terraform/10_global_backend/modules/services/lambda_layers/main.tf"
  "terraform/10_global_backend/modules/services/lambda_layers/variables.tf"
  "terraform/10_global_backend/outputs.tf"
  "terraform/10_global_backend/updated-policy.json"
  "terraform/10_global_backend/variables.tf"
)

# ──────────────────────────────────────
# Create/empty the output file
# ──────────────────────────────────────
> "$OUTPUT_FILE"

# ──────────────────────────────────────
# Dump each file
# ──────────────────────────────────────
for file in "${FILES[@]}"; do
  if [[ -f "$file" ]]; then
    echo "===== $file =====" >> "$OUTPUT_FILE"
    cat "$file" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
  else
    echo "⚠️ Warning: File not found: $file" >&2
  fi
done

echo "✅ Dump complete! See $OUTPUT_FILE"
