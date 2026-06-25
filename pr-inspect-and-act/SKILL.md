---
name: pr-inspect-and-act
description: >-
  Use when reading, inspecting, or acting on GitHub pull requests — fetching PR
  details, listing files, reading comments, checking CI, posting review comments,
  or finding PRs assigned for review. Use this instead of writing ad-hoc shell
  pipelines each time.
agents: all
version: 1
---

# gh-pr — standard commands for PR operations

All commands use the `gh` CLI. Always pass `--repo OWNER/REPO` explicitly when
not already inside that repo's working directory.

## Find PRs

```bash
# PRs where I'm requested as reviewer
gh pr list --repo OWNER/REPO --search "review-requested:mariosakka" --state open

# PRs I authored (from shared account)
gh pr list --repo OWNER/REPO --search "author:PRCreatorNR1" --state open

# All open PRs in a repo
gh pr list --repo OWNER/REPO --state open

# Single PR by number
gh pr view NUMBER --repo OWNER/REPO
```

## Get PR details (structured)

```bash
# Full metadata — title, body, author, labels, review requests, URL, CI status
gh pr view NUMBER --repo OWNER/REPO \
  --json title,body,author,additions,deletions,changedFiles,labels,reviewRequests,url,statusCheckRollup

# Just CI status
gh pr view NUMBER --repo OWNER/REPO --json statusCheckRollup
```

## List changed files

```bash
gh pr view NUMBER --repo OWNER/REPO --json files \
  --jq '.files[].path'

# With change type (added/modified/deleted) and line counts
gh pr view NUMBER --repo OWNER/REPO --json files \
  --jq '.files[] | "\(.additions)+\(.deletions)-  \(.path)"'
```

## Read comments and review threads

```bash
# All review comments (inline + summary)
gh api repos/OWNER/REPO/pulls/NUMBER/reviews

# Inline review comments only
gh api repos/OWNER/REPO/pulls/NUMBER/comments

# Issue-level comments (non-review comments on the PR)
gh api repos/OWNER/REPO/issues/NUMBER/comments
```

## Post a comment

```bash
# General comment on the PR (use this to acknowledge / signal you're looking)
gh pr comment NUMBER --repo OWNER/REPO --body "ma uit"

# Reply to a specific review thread (need the comment ID from the review comments API)
gh api repos/OWNER/REPO/pulls/NUMBER/comments \
  --method POST \
  --field body="reply text" \
  --field in_reply_to=COMMENT_ID
```

## Check CI status

```bash
gh pr checks NUMBER --repo OWNER/REPO
```

## Review actions

```bash
# Approve
gh pr review NUMBER --repo OWNER/REPO --approve --body "LGTM"

# Request changes
gh pr review NUMBER --repo OWNER/REPO --request-changes --body "reason"

# Submit a review comment without approval/rejection
gh pr review NUMBER --repo OWNER/REPO --comment --body "comment"
```

## Labels

```bash
# Add a label
gh pr edit NUMBER --repo OWNER/REPO --add-label "label-name"

# Remove a label
gh pr edit NUMBER --repo OWNER/REPO --remove-label "label-name"
```

## Quick reference

| Task | Command |
|---|---|
| PRs assigned to me | `gh pr list --repo R --search "review-requested:mariosakka"` |
| PR details + CI | `gh pr view N --repo R --json title,body,statusCheckRollup` |
| Changed file paths | `gh pr view N --repo R --json files --jq '.files[].path'` |
| All review comments | `gh api repos/R/pulls/N/comments` |
| Post acknowledgment | `gh pr comment N --repo R --body "ma uit"` |
| Check CI | `gh pr checks N --repo R` |
| Approve | `gh pr review N --repo R --approve` |

## Colete Online repos

| Short name | Full repo |
|---|---|
| platform | `Colete-Online/platform` |
| woocommerce-plugin | `Colete-Online/woocommerce-plugin` |
| prestashop-module | `Colete-Online/prestashop-module` |
| ai-tooling | `Colete-Online/ai-tooling` |
