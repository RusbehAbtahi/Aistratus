#!/usr/bin/env bash
# Download a portable Terraform v1.8.5 Windows binary into tools/
# Works in Git Bash on Windows with NO admin rights.

set -euo pipefail

TOOLS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/tools"
mkdir -p "$TOOLS_DIR"

TF_BIN="$TOOLS_DIR/terraform.exe"
if [[ -x "$TF_BIN" ]]; then
  echo "terraform.exe already present → $TF_BIN"
  exit 0
fi

echo "⬇️  Downloading Terraform v1.8.5 for Windows amd64..."
TMP_ZIP="$(mktemp -u).zip"
curl -# -L "https://releases.hashicorp.com/terraform/1.8.5/terraform_1.8.5_windows_amd64.zip" -o "$TMP_ZIP"

echo "📦  Extracting..."
unzip -q "$TMP_ZIP" terraform.exe -d "$TOOLS_DIR"
rm "$TMP_ZIP"

chmod +x "$TF_BIN"
# ← new lines start here:
cp "$TF_BIN" "${TOOLS_DIR}/terraform"
chmod +x "${TOOLS_DIR}/terraform"
# ← new lines end here

echo "✅  terraform.exe installed → $TF_BIN"
