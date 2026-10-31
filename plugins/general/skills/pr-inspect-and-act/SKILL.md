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

## Before inspecting code — read the issue, then the PR body + comments

**Always do this first, before reading the diff or touching any code.** Skipping
it means missing context another reviewer (human or bot) already surfaced,
duplicating work someone already did (e.g. re-running a manual test that a
self-review already reports doing — "verified locally: X rejected, Y allowed"),
or flagging something as a gap that's actually explicitly out of scope and
tracked in a separate follow-up issue.

1. **Find the linked issue.** Check the PR body for `Closes #N` / `Fixes #N` /
   `Resolves #N` / `Related to #N`.
2. **Read the issue** — title, body, comments, and state (open/closed). This is
   where scope, acceptance criteria, and intentional exclusions live (e.g. "RO
   hardening is out of scope here, tracked in #1039").
3. **Read the full PR body**, not just the diff — the author's own
   "What/Why/How to test" section often states exact scope and known
   limitations.
4. **Read every PR comment and review** — issue-level comments, inline review
   comments, and review summaries, including bot reviews (CodeRabbit, etc.)
   and any human self-review. A self-review claiming specific local
   verification, an explicit scope justification, or a bot flag about missing
   coverage all change what's actually left to check.
5. **Only after that**, read the diff and start functional/manual testing —
   and treat any claimed verification from step 4 as a starting point to
   confirm or challenge, not something to silently re-derive from scratch
   without mentioning it.

## Quick start — snapshot a PR

Instead of running individual `gh` commands, use:

```bash
<skill-dir>/scripts/pr-snapshot.sh OWNER/REPO NUMBER
```

(`<skill-dir>` is this skill's base directory, the folder containing this SKILL.md.)

This fires all requests in parallel and prints, **in this order**: any linked
issue(s) (parsed from `Closes/Fixes/Resolves/Related to #N` in the PR body,
with their own title/body/comments), PR summary, changed files with line
counts, review summaries (approvals/change-requests/bodies), inline review
comments, and issue-level comments on the PR. Read the linked-issue section
before the diff. Use the individual commands below only when you need specific
slices.

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
~/.desk/global/pages/<book-slug>/<name>.desk

# Workspace pages
~/.desk/workspaces/<workspace-name>/pages/<book-slug>/<name>.desk
```

Use `list_pages` (with `scope: "global"` or `scope: "workspace"`) to discover page names first, then read the file at the path above.

## After inspecting any PR — explain the test plan first

Before creating the desk page or doing anything else, **tell the user how you plan to test the changes and why.** Cover:

1. **What changed** — which files/layers are affected (client only, server only, both, DB migrations, etc.)
2. **What you will test** — the specific scenarios you'll exercise: happy path, the edge case the PR fixes, any regression risks in adjacent code
3. **How you will test it** — manual steps in the browser, running a specific test suite, calling an endpoint with curl, checking a specific UI flow, etc.
4. **Why that coverage is enough** — briefly justify why these tests would catch a regression if the fix broke something

Keep it short — a few bullet points, not a wall of text. The goal is for the user to be able to say "yes that makes sense" or "also check X" before you start.

## After inspecting any PR — always add a page to the PR reviews book

After reading or inspecting a PR, **always add a page for it to the "PR reviews" book without waiting to be asked** — never create a standalone page. `create_page` requires `filename` in `bookSlug/page.desk` format; standalone pages are not supported.

1. Call `mcp__vscode-desk__list_books` first to find the PR reviews book's slug (e.g. `pr-reviews`). If it doesn't exist yet, create it once with `mcp__vscode-desk__create_book` (title "PR reviews") and reuse that slug for every subsequent PR page — do not create a new book per PR.
2. Fetch the PR and its source issue in parallel, then create the page via `mcp__vscode-desk__create_page` with `filename: "<book-slug>/pr-{NUMBER}-{kebab-slug}.desk"`.
3. Read the page template first (`mcp__vscode-desk__get_page_template`) to understand available CSS classes.

**Required sections (in this order):**

1. **Why this existed** (`icon: 🔍`) — Explain the backstory: what was broken or missing, what prior PRs or issues led here, and why the previous behaviour was wrong. Include a callout if there's a non-obvious root cause (e.g. "pasted images become base64 URIs"). Link to related PRs and issues.

2. **What changed** (`icon: ✏️`) — A table of every changed file with a one-line description of what it does. Add a tip callout at the bottom with `+lines / -lines` and a one-line scope summary (client-only, no DB migrations, etc.).

3. **How it flows** (`icon: ⚡`) — A `.flow` diagram showing the end-to-end sequence: trigger → request → server response → client mapping → user-visible result.

4. **Source pointers** (`icon: 📂`) — A table mapping "what" to the exact file path, covering both server-side definitions and client-side entry points. Always include the server-side error code file if relevant.

5. **What's still open** (`icon: 🔮`) — Only include this section if the source issue is still open or if the PR is a partial fix. List remaining acceptance criteria and link back to the issue.

**Naming convention:** page filename `pr-{NUMBER}-{kebab-slug}.desk` inside the PR reviews book (e.g. `pr-reviews/pr-1099-order-address-validation.desk`) — never a standalone page.

**Eyebrow:** `Fix · {Layer} · {Feature}` (e.g. `Fix · Client · Tickets`)

**Subtitle:** One sentence — what the PR does and the error code or mechanism it handles.
