#!/usr/bin/env bash
# ------------------------------------------------------------------
# create_epic_gui.sh — Creates Epic 1 + 6 GUI stories, labels, milestone
# Prereqs: gh auth login  ✔, repo cloned, run from repo root
# Usage:   bash 04_scripts/gh/create_epic_gui.sh
# ------------------------------------------------------------------
set -euo pipefail

# ---------- 0.  Labels ------------------------------------------------
echo "==> Ensuring labels"
gh label create epic  --description "Parent issue that groups user stories" --color BFD4F2 2>/dev/null || true
gh label create gui   --description "Desktop GUI work"                      --color 1D76DB 2>/dev/null || true
gh label create story --description "Individual user story"                --color 7057FF 2>/dev/null || true

# ---------- 1.  Milestone ---------------------------------------------
echo "==> Ensuring milestone"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh api "repos/$REPO/milestones" \
  -f title="Intermediate Stage" \
  -f state="open" \
  -F description="All intermediate-stage work (GUI + on-demand GPU inference)" \
  > /dev/null 2>&1 || true   # Ignore 'already exists'

# ---------- 2.  Epic ---------------------------------------------------
echo "==> Creating Epic 1 – Desktop GUI core"
cat > /tmp/epic_gui.md <<'EOF'
**Epic Goal**

Deliver a cross-platform Tkinter desktop app so the user can  
• type a prompt, send it, watch live cost, and hard-stop the GPU.

**Why it matters**

GUI is the single human entry-point; even a stub forces clear API contracts.

**Acceptance**

– Stories GUI-001…GUI-006 all *Done*  
– Demo on Win/macOS: prompt → reply → cost tick  
– PO signs off on UX & cost controls
EOF

EPIC_URL=$(gh issue create \
  --title "Epic 1 – Desktop GUI core" \
  --label epic,gui \
  --body-file /tmp/epic_gui.md \
  --milestone "Intermediate Stage" | tail -n1)
EPIC_ID=${EPIC_URL##*/}
echo "Epic #$EPIC_ID created"

# ---------- 3.  Helper to spawn stories --------------------------------
create_story () {
  local id="$1" ; shift
  local title="$1" ; shift
  local body="$1"
  printf '%s\n' "$body" > /tmp/body.md
  gh issue create \
    --title "$id  $title" \
    --label gui,story \
    --body-file /tmp/body.md \
    --milestone "Intermediate Stage" \
    > /dev/null
  echo "  • $id created"
}

# ---------- 4.  Six stories --------------------------------------------
echo "==> Creating GUI stories"
create_story "GUI-001" "Prompt box accepts multi-line input" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I can enter multi-line prompts and press **Ctrl+Enter** to send.

**Acceptance**
1. Tkinter Text widget, 5 rows × 80 cols.
2. Ctrl+Enter triggers the same handler as Send.
3. Newlines preserved in JSON payload.
4. Unit test posts mock payload."

create_story "GUI-002" "Send button disables & shows spinner" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I see a spinner while inference runs, preventing duplicates.

**Acceptance**
1. Button disabled & spinner visible on click.
2. Re-enabled on success/error.
3. Unit test simulates 2-s API call."

create_story "GUI-003" "Red Stop-GPU button triggers /stop" \
"Belongs to **Epic #$EPIC_ID**

*As a cost-conscious user* I can stop the GPU within 10 s.

**Acceptance**
1. Red button (#d9534f), label \"Stop GPU\".
2. POST /stop; toast on success; error visible.
3. CloudWatch metric ManualStops increments."

create_story "GUI-004" "Idle-timeout spinbox controls auto-stop" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I set idle-timeout 1-30 min so EC2 self-stops.

**Acceptance**
1. ttk.Spinbox 1-30 min, default 5.
2. Value saved in ~/.tl-fif.ini.
3. Included in /infer JSON.
4. Functional test: 1 min → EC2 stops ~70 s later."

create_story "GUI-005" "Cost label polls live spend" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I see running € cost updated every 30 s.

**Acceptance**
1. Poll metric CurrentSpendEUR.
2. Label shows \"€ <value> (today)\".
3. Orange >€10, red >€15.
4. Unit test mocks metric endpoint."

create_story "GUI-006" "Output pane shows full conversation" \
"Belongs to **Epic #$EPIC_ID**

*As a user* I can scroll all prompts/replies with timestamps.

**Acceptance**
1. Read-only ScrolledText widget.
2. HH:MM:SS timestamps.
3. Scroll position persists.
4. Unit test verifies order & time."

echo "==> GUI epic and six stories DONE"
