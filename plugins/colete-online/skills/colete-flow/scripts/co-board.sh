#!/bin/bash
# Show open unassigned issues from the Colete Online board (top 10)
# Usage: co-board [OWNER] [REPO]
OWNER="${1:-Colete-Online}"
REPO="${2:-platform}"

echo "=== Open unassigned issues in $OWNER/$REPO ==="
echo ""
gh issue list \
  --repo "$OWNER/$REPO" \
  --state open \
  --assignee "" \
  --limit 10 \
  --json number,title,labels,createdAt \
  --jq '.[] | "#\(.number)  \(.title)  [\(.labels | map(.name) | join(", "))]"'
