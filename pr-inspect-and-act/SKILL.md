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

## Quick start — snapshot a PR

Instead of running individual `gh` commands, use:

```bash
~/.my-agent-skills/pr-inspect-and-act/scripts/pr-snapshot.sh OWNER/REPO NUMBER
```

This fires all requests in parallel and prints: summary, changed files with line counts, inline review comments, and issue-level comments. Use the individual commands below only when you need specific slices.

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

## Reading existing desk pages

There is **no `get_page` tool** in the MCP server. The only page tools are `list_pages`, `create_page`, `update_page`, and `delete_page`.

To read the content of an existing page, use the Read tool directly on the file:

```
# Global pages
~/.desk/global/pages/<name>.desk

# Workspace pages
~/.desk/workspaces/<workspace-name>/pages/<name>.desk
```

Use `list_pages` (with `scope: "global"` or `scope: "workspace"`) to discover page names first, then read the file at the path above.

## After inspecting any PR — always create a desk page

After reading or inspecting a PR, **always create a desk page for it without waiting to be asked.** Fetch the PR and its source issue in parallel first, then create the page via `mcp__vscode-desk__create_page`. Read the page template first (`mcp__vscode-desk__get_page_template`) to understand available CSS classes.

**Required sections (in this order):**

1. **Why this existed** (`icon: 🔍`) — Explain the backstory: what was broken or missing, what prior PRs or issues led here, and why the previous behaviour was wrong. Include a callout if there's a non-obvious root cause (e.g. "pasted images become base64 URIs"). Link to related PRs and issues.

2. **What changed** (`icon: ✏️`) — A table of every changed file with a one-line description of what it does. Add a tip callout at the bottom with `+lines / -lines` and a one-line scope summary (client-only, no DB migrations, etc.).

3. **How it flows** (`icon: ⚡`) — A `.flow` diagram showing the end-to-end sequence: trigger → request → server response → client mapping → user-visible result.

4. **Source pointers** (`icon: 📂`) — A table mapping "what" to the exact file path, covering both server-side definitions and client-side entry points. Always include the server-side error code file if relevant.

5. **What's still open** (`icon: 🔮`) — Only include this section if the source issue is still open or if the PR is a partial fix. List remaining acceptance criteria and link back to the issue.

**Naming convention:** `pr-{NUMBER}-{kebab-slug}.desk`

**Eyebrow:** `Fix · {Layer} · {Feature}` (e.g. `Fix · Client · Tickets`)

**Subtitle:** One sentence — what the PR does and the error code or mechanism it handles.
