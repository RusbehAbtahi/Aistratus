#!/usr/bin/env bash
REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
export PATH="$REPO_ROOT/04_scripts/no_priv/tools:$PATH"
export AWS_PAGER=""
# Auto-install portable GNU toolchain on first activation
if ! command -v make >/dev/null 2>&1; then
  echo "⚙️  Installing TinyLlama GNU toolchain (first run)…"
  bash "$( dirname "${BASH_SOURCE[0]}" )/get_portable_tools_windows.sh"
fi
echo "🔧  tinyllama no-priv toolchain active"