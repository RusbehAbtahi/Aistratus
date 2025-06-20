#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_costops.sh — Epic 6 (Cost & Monitoring) + 4 rich stories
#
# Prereqs : gh auth login ✔ • labels & milestone exist or are created here
# Usage   : bash 04_scripts/gh/create_epic_costops.sh
# ------------------------------------------------------------------
set -euo pipefail
MILESTONE="Intermediate Stage"

# ---------- 0. Ensure labels -------------------------------------------------
gh label create ops   --description "Cost & monitoring work"              --color 95A5A6 2>/dev/null || true
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create story --description "Individual user story"               --color 7057FF 2>/dev/null || true

# ---------- 1. Epic body ------------------------------------------------------
cat > /tmp/epic_ops.md <<'EOF'
**Epic Goal**

Implement a lightweight **observability and cost-guardrail layer** that:

* Publishes a live spend metric the GUI can poll (`CurrentSpendEUR`).  
* Shows GPU utilisation, latency, and queue depth on a single CloudWatch dashboard.  
* Fires budget alarms at €15 (warning) and €20 (hard stop → auto-shutdown).  
* Provides a manual, GUI-exposed emergency “Stop GPU” that always works.

**Why this matters**

TinyLlama’s competitive edge is *running cheaply*.  
Every hour of forgotten GPU time destroys that promise.  
Early, automated cost-signals keep the PO confident and prevent end-of-month surprises, while dashboards help diagnose latency spikes long before users complain.

**Success / Acceptance**

1. GUI sees spend updates every 30 s via Lambda metric proxy.  
2. When monthly spend hits €15 a Slack/email alert fires; at €20 a Lambda stops EC2.  
3. CloudWatch dashboard shows: GPU util%, VRAM%, p95 latency, queue depth, spend.  
4. All guardrails IaC-defined; no manual console tweaks.
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 6 – Cost governance & monitoring" \
  --label epic,ops \
  --body-file /tmp/epic_ops.md \
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
    --label ops,story --milestone "$MILESTONE" \
    --body-file "$tmp" >/dev/null
  rm "$tmp"
  echo "   • ${code} created"
}

# ---------- 3. Stories -------------------------------------------------------
make_story OPS-001 "Publish custom metric CurrentSpendEUR" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a cost-aware user*  
I want the GUI to display live AWS spend in Euros, refreshed every 30 seconds,  
so I instantly see the impact of long sessions or mistakes.

**Details / Acceptance**

1. Lambda `cost_publisher.py` calls Cost Explorer → `put_metric_data` into namespace `TLFIF/Cost`.  
2. Metric name `CurrentSpendEUR`, value rounded to €0.01.  
3. Cron Schedule: EventBridge rule every **15 min** (cost calls are rate-limited).  
4. GUI polls a lightweight `/cost` route that returns the latest datapoint.  
5. README documents how to enable Cost Explorer API for new accounts.
EOF

make_story OPS-002 "Budget alarms €15 warn / €20 auto-stop" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As the budget owner*  
I need AWS Budgets to warn me at €15 and hard-stop the GPU at €20  
so monthly spend can never exceed a pizza night.

**Details / Acceptance**

1. Budget name `TinyLlama-Monthly`. Period: Calendar month. Scope: entire account.  
2. SNS topic `budget-alerts`. Email subscription `rusbeh@…`.  
3. Warning action: SNS email at 75 %.  
4. Hard-stop action: SNS → Lambda `budget_killer.py` → `ec2:StopInstances` on tag `env=tinyllama`.  
5. PR includes Terraform or CloudFormation template + README test steps.
EOF

make_story OPS-003 "Unified CloudWatch dashboard" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As an operator*  
I want a single CloudWatch dashboard showing GPU utilisation, VRAM %, queue depth, p95 latency, and CurrentSpendEUR  
so that I can correlate performance with cost in one glance.

**Details / Acceptance**

1. Dashboard name `TLFIF-Intermediate`.  
2. Widgets: (a) line GPU util %, (b) line VRAM %, (c) single-value p95 latency, (d) bar queue depth, (e) line spend €.  
3. JSON dashboard definition committed to `05_docs/02_architecture/cloudwatch_dashboard.json`.  
4. Screenshot attached to issue on completion.
EOF

make_story OPS-004 "GUI emergency Stop GPU always functional" <<'EOF'
Belongs to **Epic #'"$EPIC_ID"**

**User Story**

*As a nervous user*  
I need the red “Stop GPU” button to work even if Redis or Lambda are broken,  
so I can guarantee runaway costs end in <10 s.

**Details / Acceptance**

1. GUI button calls dedicated `/stop` route → API Gateway directly hits Lambda with short timeout.  
2. Lambda bypasses Redis and calls `StopInstances` unconditionally.  
3. GUI shows spinner and success/fail toast.  
4. Chaos-test: kill Redis; press Stop GPU → instance stops, metric `ManualStops` +1.
EOF

echo "🎉  Epic 6 and four richly-described stories created"
