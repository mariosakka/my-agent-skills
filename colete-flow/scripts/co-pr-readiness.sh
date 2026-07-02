#!/bin/bash
# Run all pre-PR checks before calling co-pr
# Usage: co-pr-readiness [REPO] [ISSUE_NUMBER]
REPO="${1:-Colete-Online/platform}"
ISSUE_NUMBER="${2:-}"
PASS=true

echo "=== co-pr readiness check for $REPO ==="
echo ""

# 1. Branch from development
BASE="development"
if ! git merge-base --is-ancestor "$BASE" HEAD 2>/dev/null; then
  echo "✗ Branch is NOT based on $BASE"
  PASS=false
else
  CURRENT=$(git branch --show-current)
  echo "✓ Branch '$CURRENT' is based on $BASE"
fi

# 2. No uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
  echo "✗ Uncommitted changes present:"
  git status --short
  PASS=false
else
  echo "✓ Working tree clean"
fi

# 3. Issue number
if [ -z "$ISSUE_NUMBER" ]; then
  echo "⚠ No issue number supplied (pass as second arg)"
else
  echo "✓ Issue number: $ISSUE_NUMBER"
fi

# 4. co-pr available
if ! command -v co-pr &>/dev/null; then
  echo "✗ co-pr not found in PATH"
  PASS=false
else
  echo "✓ co-pr available"
fi

# 5. gh auth
if ! gh auth status &>/dev/null; then
  echo "✗ gh: not authenticated"
  PASS=false
else
  ACTOR=$(gh api user --jq '.login' 2>/dev/null)
  echo "✓ gh authenticated as: $ACTOR"
fi

echo ""
if [ "$PASS" = true ]; then
  echo "All checks passed — ready to run: co-pr $ISSUE_NUMBER"
else
  echo "Fix the above issues before calling co-pr."
  exit 1
fi
