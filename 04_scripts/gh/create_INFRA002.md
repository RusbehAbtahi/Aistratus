#!/usr/bin/env bash
set -euo pipefail

TITLE="INFRA-002 - Global ID registry via SSM Parameter Store (Option 1)"
BRANCH="feature/INFRA-002-ssm-param-switch"
REPO="git@github.com:RusbehAbtahi/tinyllama.git"

BODY=$(cat <<'EOF'
### 🎯 Goal
Move **all hard-coded AWS resource IDs** … 
EOF
)

echo "Creating GitHub issue…"
ISSUE_URL=$(gh issue create --repo "$REPO" --title "$TITLE" --body "$BODY" --label "epic:platform,terraform,backend,size:S-2")
echo "Issue: $ISSUE_URL"

echo "Creating branch…"
git checkout -b "$BRANCH"
git push -u origin "$BRANCH"

echo "Opening draft PR…"
gh pr create --repo "$REPO" --title "$TITLE" --body "Closes $ISSUE_URL" --base main --head "$BRANCH" --draft
