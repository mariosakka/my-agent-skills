#!/usr/bin/env bash
#
# Deterministically fetch candidate GitHub issues for a staleness/overlap
# audit: unassigned issues carrying a given label (default: "approved"),
# either straight from `gh issue list` or filtered through a Projects
# board column.
#
# Output: JSON array on stdout, one object per candidate:
#   { number, title, url, labels, body, createdAt, updatedAt }
#
# No LLM judgment happens in this script — it is pure gh/jq filtering so
# results are reproducible. Staleness/overlap evaluation is a separate,
# agent-driven step (see ../SKILL.md).

set -euo pipefail

REPO=""
BOARD=0
OWNER=""
PROJECT_NUMBER=""
STATUS="Todo"
LABELS=()
STATE="open"
INCLUDE_ASSIGNED=0
OUT=""

usage() {
  cat <<'EOF'
Usage:
  Plain mode (no board):
    fetch-candidates.sh [--repo OWNER/REPO] [--label LABEL ...] [--state open|closed|all] [--include-assigned] [--out FILE]

  Board mode:
    fetch-candidates.sh --board --owner ORG --project NUMBER [--status "Todo"] [--repo OWNER/REPO] [--label LABEL ...] [--include-assigned] [--out FILE]

Defaults: --label approved, --state open, --status Todo, unassigned-only.
--repo defaults to the repo of the current directory (gh auto-detects).
--label may be passed multiple times; an issue must carry ALL of them.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --board) BOARD=1; shift ;;
    --owner) OWNER="$2"; shift 2 ;;
    --project) PROJECT_NUMBER="$2"; shift 2 ;;
    --status) STATUS="$2"; shift 2 ;;
    --label) LABELS+=("$2"); shift 2 ;;
    --state) STATE="$2"; shift 2 ;;
    --include-assigned) INCLUDE_ASSIGNED=1; shift ;;
    --out) OUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ ${#LABELS[@]} -eq 0 ]]; then
  LABELS=("approved")
fi

REPO_ARGS=()
if [[ -n "$REPO" ]]; then
  REPO_ARGS=(--repo "$REPO")
fi

labels_json=$(printf '%s\n' "${LABELS[@]}" | jq -R . | jq -s .)

if [[ "$BOARD" -eq 1 ]]; then
  if [[ -z "$OWNER" || -z "$PROJECT_NUMBER" ]]; then
    echo "--board requires --owner and --project" >&2
    exit 1
  fi

  # 1. Pull the board, keep items in the target status column, apply the
  #    assignee filter (deterministic, no gh issue calls needed yet).
  candidates_numbers=$(gh project item-list "$PROJECT_NUMBER" --owner "$OWNER" \
    --format json --limit 500 \
    | jq -r --arg status "$STATUS" --argjson includeAssigned "$INCLUDE_ASSIGNED" '
        .items[]
        | select(.status == $status)
        | select($includeAssigned == 1 or ((.assignees // []) | length == 0))
        | .content.number
        | select(. != null)
      ')

  if [[ -z "$candidates_numbers" ]]; then
    echo "[]"
    exit 0
  fi

  # 2. Hydrate each candidate with labels/body/etc via gh issue view, then
  #    filter by required labels.
  results="[]"
  while IFS= read -r num; do
    [[ -z "$num" ]] && continue
    issue_json=$(gh issue view "$num" "${REPO_ARGS[@]}" \
      --json number,title,url,labels,body,createdAt,updatedAt,state 2>/dev/null) || continue
    issue_state=$(echo "$issue_json" | jq -r '.state')
    [[ "$issue_state" != "OPEN" ]] && continue
    # Require ALL of $need to be present in the issue's labels.
    has_all=$(echo "$issue_json" | jq --argjson need "$labels_json" '
        ($need - [.labels[].name]) | length == 0
      ')
    if [[ "$has_all" == "true" ]]; then
      results=$(echo "$results" | jq --argjson item "$issue_json" '. + [$item]')
    fi
  done <<< "$candidates_numbers"

  output="$results"
else
  # Plain mode: gh issue list already gives us assignees + labels in one call.
  all_json=$(gh issue list "${REPO_ARGS[@]}" --state "$STATE" \
    --json number,title,url,labels,assignees,body,createdAt,updatedAt --limit 500)

  output=$(echo "$all_json" | jq --argjson need "$labels_json" --argjson includeAssigned "$INCLUDE_ASSIGNED" '
      [ .[]
        | select($includeAssigned == 1 or ((.assignees // []) | length == 0))
        | select(($need - [.labels[].name]) | length == 0)
      ]
    ')
fi

if [[ -n "$OUT" ]]; then
  echo "$output" | jq . > "$OUT"
  echo "Wrote $(echo "$output" | jq 'length') candidate(s) to $OUT" >&2
else
  echo "$output" | jq .
fi
