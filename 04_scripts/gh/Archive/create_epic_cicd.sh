#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_cicd.sh — Epic 7 (CI/CD & AMI pipeline) + 4 rich stories
#
# Prereqs : gh auth login ✔ • milestone exists
# Usage   : bash 04_scripts/gh/create_epic_cicd.sh
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create cicd  --description "CI/CD pipeline work"                --color 27AE60 2>/dev/null || true
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story --description "Individual user story"              --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_cicd.md <<'EOF'
**Epic Goal**

Create a **single-click CI/CD pipeline** that:

1. Builds and unit-tests code on every push to *main*.  
2. Bakes a new GPU AMI via EC2 Image Builder on successful tests.  
3. Requires human approval for AMI promotion.  
4. Deploys updated Lambda Router automatically.  
5. Publishes artefacts and pipeline status badges back to GitHub.

**Why this matters**

Manual deployments are error-prone and slow.  
A codified pipeline:

* Makes every infra change reviewable and reproducible.  
* Provides instant feedback on unit-test regressions.  
* Gives us a rollback “easy button” (re-point LaunchTemplate to previous AMI).  

Without a robust pipeline, we risk snowballing drift between docs, code, and production.

**Success / Acceptance**

* Pushing a commit to *main* triggers CodePipeline ➔ green end-to-end run.  
* A failed unit test halts the pipeline; no AMI or Lambda deploy occurs.  
* Previous AMI versions (last 5) remain available for rollback.  
* Pipeline cost ≤ €0.03 per run (graviton CodeBuild, short Image Builder step).
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 7 – CI/CD & AMI pipeline" \
  --label epic,cicd \
  --body-file /tmp/epic_cicd.md \
  --milestone "$MILESTONE" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "✅  Epic #$EPIC_ID created"

# ---------- 2. Helper --------------------------------------------------------
make_story () {
  local code="$1"; shift
  local title="$1"; shift
  local tmp; tmp=$(mktemp)
  cat > "$tmp"
  gh issue create --title "${code}  ${title}" \
    --label cicd,story --milestone "$MILESTONE" \
    --body-file "$tmp" >/dev/null
  rm "$tmp"
  echo "   • ${code} created"
}

# ---------- 3. Stories -------------------------------------------------------
make_story CI-001 "Pipeline triggers on every push to main" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a developer*  
I want CodePipeline to start automatically whenever a commit lands on the *main* branch,  
so that every change—code or documentation—passes tests before merging into production.

**Details / Acceptance**

1. CodeStar Connections links GitHub repo to AWS.  
2. Source stage watches `refs/heads/main`.  
3. Webhook trigger verified by pushing a dummy commit; pipeline initiates within 30 s.  
4. README badge shows latest pipeline status (`passing` / `failing`).
EOF

make_story CI-002 "CodeBuild stage runs unit tests ≥ 90 % coverage" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a quality advocate*  
I want CodeBuild to run `pytest` with coverage enforced at **90 %**  
so that regressions are caught before deployment.

**Details / Acceptance**

1. `buildspec.yml` installs deps, runs `pytest --cov=.`.  
2. Coverage threshold enforced via `coverage xml && coverage html`.  
3. Failing tests ➔ pipeline stops; GitHub commit status set to `failure`.  
4. Artifacts: `coverage.html` uploaded to S3 for inspection.
EOF

make_story CI-003 "Image Builder stage bakes GPU AMI" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a release engineer*  
I want a dedicated Image Builder stage that creates a versioned AMI  
so every deployment is traceable and repeatable.

**Details / Acceptance**

1. CodeBuild calls `aws imagebuilder start-image-pipeline-execution`.  
2. On success, SSM Param `/tl-fif/latest_ami_id` updated automatically.  
3. Image recipe & pipeline defined in `infra/imagebuilder/` IaC folder.  
4. Average bake time ≤ 12 min on m7g.large builder instance.
EOF

make_story CI-004 "Auto-deploy Lambda Router + easy rollback" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As an operator*  
I need the pipeline to publish a new Lambda version, shift the `prod` alias,  
and provide a one-click rollback to the previous version  
so I can recover instantly from bad deploys.

**Details / Acceptance**

1. Post-build: `zip` Lambda → `aws lambda publish-version`.  
2. `aws lambda update-alias --function-name lambda_router --name prod --function-version <new>`  
3. Previous 5 versions retained; rollback doc in README.  
4. Success notification posted to Slack/#deploys (SNS).
EOF

echo "🎉  Epic 7 and four richly-described stories created"
