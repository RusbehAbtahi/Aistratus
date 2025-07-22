#!/usr/bin/env bash
set -euo pipefail

LAMBDA_NAME="tlfif-default-router"

echo "⟹ Fetching download URL for ${LAMBDA_NAME} ..."
URL=$(aws lambda get-function \
        --function-name "${LAMBDA_NAME}" \
        --query 'Code.Location' \
        --output text)

TMPDIR=$(mktemp -d)
ZIP_PATH="${TMPDIR}/router.zip"

echo "⟹ Downloading ZIP to ${ZIP_PATH} ..."
curl -sSL -o "${ZIP_PATH}" "${URL}"

echo "⟹ Listing ZIP contents (first 50 lines) ..."
unzip -Z1 "${ZIP_PATH}" | head -n 50

# Find the first match for jwt_tools.py (path inside ZIP can vary)
REL_PATH=$(unzip -Z1 "${ZIP_PATH}" | grep -m1 'jwt_tools.py') || {
  echo "ERROR: jwt_tools.py not found in ZIP" >&2
  exit 1
}

echo
echo "===== BEGIN jwt_tools.py (${REL_PATH}) ====="
unzip -p "${ZIP_PATH}" "${REL_PATH}"
echo "===== END jwt_tools.py ====="

echo
echo "⟹ Done. Temp dir preserved at ${TMPDIR} (delete when finished)."
