#!/bin/bash
# Fetch all PR data in one shot (parallel requests)
# Usage: pr-snapshot OWNER/REPO PR_NUMBER
REPO="${1:?Usage: pr-snapshot OWNER/REPO NUMBER}"
PR="${2:?Usage: pr-snapshot OWNER/REPO NUMBER}"
TMP=$(mktemp -d)

echo "=== PR #$PR — $REPO ==="
echo ""

gh pr view "$PR" --repo "$REPO" \
  --json title,body,author,additions,deletions,changedFiles,labels,reviewRequests,url,statusCheckRollup,files \
  > "$TMP/main.json" &
PID1=$!

gh api "repos/$REPO/pulls/$PR/comments" > "$TMP/review-comments.json" &
PID2=$!

gh api "repos/$REPO/issues/$PR/comments" > "$TMP/issue-comments.json" &
PID3=$!

wait $PID1 $PID2 $PID3

echo "--- Summary ---"
cat "$TMP/main.json" | jq '{
  title,
  body,
  author: .author.login,
  additions,
  deletions,
  changedFiles,
  labels: [.labels[].name],
  url,
  ci: [.statusCheckRollup[] | {name: .name, state: .state}]
}'

echo ""
echo "--- Changed Files ---"
cat "$TMP/main.json" | jq -r '.files[] | "+\(.additions) -\(.deletions)  \(.path)"'

echo ""
echo "--- Inline Review Comments ---"
cat "$TMP/review-comments.json" | jq -r '.[] | "[\(.path):\(.line // "?")] \(.user.login): \(.body)"' 2>/dev/null || echo "(none)"

echo ""
echo "--- Issue-level Comments ---"
cat "$TMP/issue-comments.json" | jq -r '.[] | "[\(.user.login)] \(.body)"' 2>/dev/null || echo "(none)"

rm -rf "$TMP"
