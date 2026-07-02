#!/bin/bash
# Compare issue estimation to branch age in hours
# Usage: co-estimate-check OWNER/REPO ISSUE_NUMBER
REPO="${1:?Usage: co-estimate-check OWNER/REPO ISSUE_NUMBER}"
ISSUE="${2:?Usage: co-estimate-check OWNER/REPO ISSUE_NUMBER}"

# Parse "Estimation: Xh" or "Estimation: X hours" from issue body
BODY=$(gh issue view "$ISSUE" --repo "$REPO" --json body --jq '.body' 2>/dev/null)
ESTIMATE_H=$(echo "$BODY" | grep -i 'estimation' | grep -oE '[0-9]+' | head -1)

if [ -z "$ESTIMATE_H" ]; then
  echo "⚠ No 'Estimation:' field found in issue #$ISSUE body"
  echo "Issue body excerpt:"
  echo "$BODY" | head -10
  exit 0
fi

echo "Estimated: ${ESTIMATE_H}h"

# Branch age from first commit on branch relative to development
FIRST_COMMIT_DATE=$(git log --reverse --format="%ct" development..HEAD 2>/dev/null | head -1)
if [ -z "$FIRST_COMMIT_DATE" ]; then
  echo "⚠ No commits ahead of development — branch age unknown"
  exit 0
fi

NOW=$(date +%s)
ELAPSED_H=$(( (NOW - FIRST_COMMIT_DATE) / 3600 ))
echo "Elapsed : ${ELAPSED_H}h since first commit"

THRESHOLD=$(( ESTIMATE_H / 2 ))
if [ "$ELAPSED_H" -gt "$ESTIMATE_H" ]; then
  echo "✗ OVER ESTIMATE by $((ELAPSED_H - ESTIMATE_H))h — update the issue estimate"
  exit 1
elif [ "$ELAPSED_H" -gt "$THRESHOLD" ]; then
  echo "⚠ Past 50% of estimate (${ELAPSED_H}h / ${ESTIMATE_H}h)"
else
  echo "✓ Within estimate (${ELAPSED_H}h / ${ESTIMATE_H}h)"
fi
