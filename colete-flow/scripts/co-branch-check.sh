#!/bin/bash
# Verify current branch is based on development and show ahead/behind counts
BASE="development"
CURRENT=$(git branch --show-current)
AHEAD=$(git log --oneline "$BASE..HEAD" 2>/dev/null | wc -l | tr -d ' ')
BEHIND=$(git log --oneline "HEAD..$BASE" 2>/dev/null | wc -l | tr -d ' ')

echo "Branch  : $CURRENT"
echo "Ahead of $BASE : $AHEAD commit(s)"
echo "Behind $BASE   : $BEHIND commit(s)"

if ! git merge-base --is-ancestor "$BASE" HEAD 2>/dev/null; then
  echo ""
  echo "✗ ERROR: current branch does NOT descend from $BASE"
  exit 1
fi
echo "✓ Branch is based on $BASE"

STAGED=$(git diff --cached --name-only 2>/dev/null)
if [ -n "$STAGED" ]; then
  echo ""
  echo "Staged files:"
  echo "$STAGED"
fi
