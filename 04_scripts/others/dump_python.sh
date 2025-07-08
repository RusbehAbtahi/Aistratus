#!/usr/bin/env bash
set -euo pipefail

OUTFILE="all_project_code.txt"
> "$OUTFILE"

# List of files (excluding app.py)
files=(
"01_src/tinyllama/gui/app_state.py"
"01_src/tinyllama/gui/main.py"
"01_src/tinyllama/gui/gui_view.py"
"01_src/tinyllama/gui/thread_service.py"
"01_src/tinyllama/gui/controllers/auth_controller.py"
"01_src/tinyllama/gui/controllers/cost_controller.py"
"01_src/tinyllama/gui/controllers/gpu_controller.py"
"01_src/tinyllama/gui/controllers/prompt_controller.py"
"api/config.py"
"api/routes.py"
"api/security.py"
"01_src/tinyllama/router/handler.py"
"01_src/tinyllama/utils/auth.py"
"01_src/tinyllama/utils/jwt_tools.py"
"01_src/tinyllama/utils/ssm.py"
"01_src/tinyllama/utils/verify_jwt.py"
"lambda_entry.py"
)

for file in "${files[@]}"; do
  if [[ -f "$file" ]]; then
    echo "##### $file #####" >> "$OUTFILE"
    cat "$file" >> "$OUTFILE"
    echo -e "\n\n" >> "$OUTFILE"
  else
    echo "##### $file (NOT FOUND) #####\n" >> "$OUTFILE"
  fi
done

echo "Done. Output saved to $OUTFILE"
