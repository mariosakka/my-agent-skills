#!/usr/bin/env bash
#
# Deterministically fetch the two PR audit sets for a given user:
#
#   authored   - open (incl. draft) PRs that "belong" to the user: the user
#                is a PR assignee, OR the user is assigned to the issue the
#                PR closes. NOTE: in this org PRs are opened from shared/bot
#                accounts (PRCreatorNR1, Devify101, ...), so `author.login`
#                is USELESS for finding "my" PRs -- assignee is the signal.
#   to-review  - open PRs where the user is a currently-requested reviewer
#                and hasn't submitted a review yet (GitHub's
#                review-requested:USER search already excludes PRs where
#                the request was resolved by a submitted review).
#
# For `authored`, each PR is additionally hydrated with:
#   - reviewsReceived: distinct latest review per human reviewer (bot logins
#     and the PR's own assignees are excluded from the "human" count, but
#     still reported separately as botReviews)
#   - reviewersRequested: logins still pending a review
#   - wasPutBackToDraft: true if a CONVERT_TO_DRAFT_EVENT ever fired on the
#     PR's timeline (only possible if it was Ready for review at some point)
#
# Output: JSON array on stdout (or --out FILE). No LLM judgment here --
# pure gh/jq. Deciding what to DO about a stale review request, a PR stuck
# in draft, etc. is the agent-driven step in ../SKILL.md.
#
# Implementation note: intermediate PR sets are accumulated as one-JSON-
# object-per-line files (jsonl), not grown as shell variables passed via
# `jq --argjson`. Growing a JSON blob through repeated --argjson calls
# re-embeds the whole (growing) blob as a command-line argument on every
# iteration, which is O(n^2) and blows past ARG_MAX once bodies/reviews
# accumulate across ~100+ PRs. Files avoid both problems: jq reads them
# directly, not through argv.

set -euo pipefail

MODE=""
REPO=""
GH_USER=""
OUT=""

usage() {
  cat <<'EOF'
Usage:
  fetch-pr-audit.sh --mode authored  --repo OWNER/REPO [--user LOGIN] [--out FILE]
  fetch-pr-audit.sh --mode to-review --repo OWNER/REPO [--user LOGIN] [--out FILE]

--user defaults to the currently authenticated gh user (gh api user -q .login).
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --user) GH_USER="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$MODE" || -z "$REPO" ]]; then
  echo "--mode and --repo are required" >&2
  usage
  exit 1
fi

if [[ -z "$GH_USER" ]]; then
  GH_USER="$(gh api user -q .login)"
fi

OWNER="${REPO%%/*}"
NAME="${REPO##*/}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

case "$MODE" in
  to-review)
    output=$(gh pr list --repo "$REPO" --search "review-requested:$GH_USER" \
      --state open \
      --json number,title,url,author,isDraft,createdAt,updatedAt,reviewRequests,reviews \
      --limit 200 \
      | jq --arg u "$GH_USER" '
          [ .[] | {
              number, title, url, isDraft, createdAt, updatedAt,
              author: .author.login,
              reviewersRequested: [.reviewRequests[].login],
              reviewsAlreadyReceived: [.reviews[] | {login: .author.login, state}]
            }
          ]
        ')
    ;;

  authored)
    gh pr list --repo "$REPO" --state open \
      --json number,title,url,author,assignees,isDraft,body,createdAt,updatedAt,reviewRequests,reviews \
      --limit 200 > "$WORKDIR/all.json"

    jq --arg u "$GH_USER" '
        [.[] | select((.assignees // []) | map(.login) | index($u) != null)]
      ' "$WORKDIR/all.json" > "$WORKDIR/direct.json"

    jq --arg u "$GH_USER" '
        [.[] | select((.assignees // []) | map(.login) | index($u) == null)]
      ' "$WORKDIR/all.json" > "$WORKDIR/others.json"

    # Candidates not directly assigned: check whether the issue the PR
    # closes (via "Closes/Fixes/Resolves #N" in the body) is assigned to
    # the user. Each qualifying PR is appended as its own line/file --
    # never re-embedded into a growing shell variable.
    : > "$WORKDIR/via_issue.jsonl"
    while IFS= read -r pr; do
      [[ -z "$pr" || "$pr" == "null" ]] && continue
      body=$(echo "$pr" | jq -r '.body // ""')
      issue_num=$(echo "$body" \
        | grep -ioE '(close[sd]?|fix(e[sd])?|resolve[sd]?)[[:space:]]+#[0-9]+' \
        | grep -oE '[0-9]+' | head -1 || true)
      [[ -z "$issue_num" ]] && continue
      is_assigned=$(gh issue view "$issue_num" --repo "$REPO" \
        --json assignees 2>/dev/null \
        | jq --arg u "$GH_USER" '[.assignees[].login] | index($u) != null' \
        2>/dev/null || echo false)
      if [[ "$is_assigned" == "true" ]]; then
        echo "$pr" >> "$WORKDIR/via_issue.jsonl"
      fi
    done < <(jq -c '.[]' "$WORKDIR/others.json")

    jq -s 'add' "$WORKDIR/direct.json" <(jq -s '.' "$WORKDIR/via_issue.jsonl") \
      > "$WORKDIR/candidates.json"

    # Hydrate: reviewer split (human vs bot) + draft-demotion history.
    : > "$WORKDIR/result.jsonl"
    while IFS= read -r pr; do
      [[ -z "$pr" || "$pr" == "null" ]] && continue
      number=$(echo "$pr" | jq -r '.number')

      # NOTE: timelineItems.totalCount ignores the itemTypes filter (a known
      # GitHub GraphQL quirk) and returns the count of ALL timeline events on
      # the PR, not just matching ones -- so count the returned `nodes`
      # instead, never totalCount, for a type-filtered timelineItems query.
      demoted_count=$(gh api graphql -f query='
        query($owner:String!, $repo:String!, $num:Int!) {
          repository(owner:$owner, name:$repo) {
            pullRequest(number:$num) {
              timelineItems(first: 100, itemTypes: [CONVERT_TO_DRAFT_EVENT]) {
                nodes { __typename }
              }
            }
          }
        }' -f owner="$OWNER" -f repo="$NAME" -F num="$number" \
        -q '.data.repository.pullRequest.timelineItems.nodes | length' 2>/dev/null || echo 0)
      demoted_count="${demoted_count:-0}"

      echo "$pr" | jq --arg u "$GH_USER" --argjson demoted "$demoted_count" '
          {
            number, title, url, isDraft, createdAt, updatedAt,
            reviewersRequested: [.reviewRequests[].login],
            wasPutBackToDraft: ($demoted > 0)
          } + (
            (.reviews // []) as $reviews
            | ($reviews | map(select(.author.login != $u))) as $notMine
            | {
                botReviews: [$notMine[] | select(.author.login == "coderabbitai" or (.author.login | endswith("[bot]"))) | {login: .author.login, state}],
                humanReviews: [$notMine[] | select(.author.login != "coderabbitai" and ((.author.login | endswith("[bot]")) | not)) | {login: .author.login, state}]
              }
          )
        ' >> "$WORKDIR/result.jsonl"
    done < <(jq -c '.[]' "$WORKDIR/candidates.json")

    output=$(jq -s '.' "$WORKDIR/result.jsonl")
    ;;

  *)
    echo "Unknown --mode '$MODE'. Use 'authored' or 'to-review'." >&2
    exit 1
    ;;
esac

if [[ -n "$OUT" ]]; then
  echo "$output" | jq . > "$OUT"
  echo "Wrote $(echo "$output" | jq 'length') PR(s) to $OUT" >&2
else
  echo "$output" | jq .
fi
