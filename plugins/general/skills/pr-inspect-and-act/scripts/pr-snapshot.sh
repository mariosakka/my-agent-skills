#!/bin/bash
# Fetch all PR data in one shot (parallel requests) — issue first, then PR
# body/files/comments/reviews. Read the linked-issue section before the diff.
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

gh api "repos/$REPO/pulls/$PR/reviews" > "$TMP/reviews.json" &
PID4=$!

wait $PID1 $PID2 $PID3 $PID4

# Extract linked issue numbers (Closes/Fixes/Resolves/Related to #N) from the
# PR body and fetch each one — this must be read before the diff.
ISSUE_NUMS=$(jq -r '.body' "$TMP/main.json" \
  | grep -ioE '(closes|fixes|resolves|related to)[[:space:]]*#[0-9]+' \
  | grep -oE '[0-9]+' | sort -u)

if [[ -n "$ISSUE_NUMS" ]]; then
  echo "--- Linked Issue(s) ---"
  for n in $ISSUE_NUMS; do
    gh issue view "$n" --repo "$REPO" \
      --json number,title,state,labels,body,comments \
      | jq '{
          number, title, state,
          labels: [.labels[].name],
          body,
          comments: [.comments[] | {author: .author.login, body}]
        }'
    echo ""
  done
else
  echo "--- Linked Issue(s) ---"
  echo "(none found in PR body — check manually if this PR should reference one)"
  echo ""
fi

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
echo "--- Reviews (approvals / change requests / summaries) ---"
cat "$TMP/reviews.json" | jq -r '.[] | "[\(.state)] \(.user.login): \(.body)"' 2>/dev/null || echo "(none)"

echo ""
echo "--- Inline Review Comments ---"
cat "$TMP/review-comments.json" | jq -r '.[] | "[\(.path):\(.line // "?")] \(.user.login): \(.body)"' 2>/dev/null || echo "(none)"

echo ""
echo "--- Issue-level Comments (on the PR itself) ---"
cat "$TMP/issue-comments.json" | jq -r '.[] | "[\(.user.login)] \(.body)"' 2>/dev/null || echo "(none)"

rm -rf "$TMP"
