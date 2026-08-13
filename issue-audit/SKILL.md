---
name: issue-audit
description: >-
  Audit approved, unassigned GitHub issues (from a repo's issue list or a
  Projects board column) for staleness against the current codebase and
  for overlap with other open issues/PRs. Use when Mario asks to "check if
  these issues are still valid", "find stale issues", "see if any board
  issues are already fixed or covered by another PR", "clean up the
  backlog", "audit approved issues", or before picking a Todo-column issue
  to confirm it's still worth doing. NOT for triaging brand-new/unlabeled
  issues or for issues already assigned/in-progress.
triggers:
  - stale issues
  - audit approved issues
  - clean up the backlog
  - is this issue still valid
  - overlapping issues or PRs
  - before picking up a board issue
agents: all
version: 1
---

# issue-audit — find backlog issues that are stale or overlapping

Splits into two phases: a **deterministic fetch** (script, no LLM judgment)
and an **agent-driven validation** (you read code/issues/PRs and decide).
Never skip straight to judgment without running the script first — the
candidate list must be reproducible, not vibes-based.

## Phase 1 — Fetch candidates (script only)

Run `scripts/fetch-candidates.sh`. It filters by label (default `approved`)
and unassigned status, either directly (`gh issue list`) or through a
Projects board column (`--board`). It does no evaluation — pure `gh`/`jq`.

```bash
# Board mode (Todo column, e.g. Colete-Online/platform's "Dev" project #1)
scripts/fetch-candidates.sh --board --owner Colete-Online --project 1 \
  --status Todo --label approved --out /tmp/candidates.json

# Plain mode (no board involved)
scripts/fetch-candidates.sh --repo OWNER/REPO --label approved --out /tmp/candidates.json
```

Run `scripts/fetch-candidates.sh --help` for all flags (state, multiple
`--label`, `--include-assigned`, etc).

Each candidate in the output JSON has: `number`, `title`, `url`, `labels`,
`body`, `createdAt`, `updatedAt`.

## Phase 2 — Validate each candidate (agent judgment)

**Sync first — always.** Run `git fetch origin` (or `--all` in a
multi-remote setup) before reading any file or `git log`. The local
checkout can be behind the remote default branch (`development` for
platform) even when it looks clean — a stale checkout means "the code
still matches" is a claim about an old snapshot, not the repo. Check with
`git rev-list --left-right --count origin/<branch>...<branch>`; if it
reports anything on the left, the local branch is behind. Read files and
run `git log`/`git log -S` against `origin/<branch>` (e.g.
`git show origin/development:<path>`, `git log origin/development -- <path>`),
not the working tree, so a feature branch or a behind-by-N checkout can't
silently produce a wrong verdict.

For every candidate, answer two independent questions, then give a verdict.
Do this per-issue — don't batch-skim titles and guess.

**1. Is it still accurate against the current codebase?**
- Read the issue body for the files/behavior/error it describes.
- Read those files as they exist at `origin/<branch>` (`Read`/`Grep` the
  working tree only after confirming step above that it's not behind, or
  use `git show origin/<branch>:<path>` directly), not from memory.
- Check `git log origin/<branch> -- <path>` / `git log --oneline -S"<symbol>" origin/<branch> -- <path>`
  for commits touching that area since the issue was filed (`createdAt`).
- A commit touching the area is not proof it's fixed — read the diff/current
  code and confirm the described symptom is actually gone or actually still
  present.

**2. Does it overlap with another open issue or PR?**
- Search issues: `gh issue list --search "<keywords>" --state all`.
- Search PRs: `gh pr list --search "<keywords>" --state all`, and check
  cross-references: `gh api graphql` timelineItems on the issue (see
  `co-ops:pr-merge-check` or prior conversation pattern) for
  `CROSS_REFERENCED_EVENT`/`CONNECTED_EVENT` PRs.
- Overlap can be partial (a PR fixes one of several sub-problems the issue
  lists) or full (a PR/issue already covers the entire thing).

**Verdict per issue** — report one of:
- `STILL VALID` — code still matches the description, no overlap found.
- `STALE — FIXED` — the described problem no longer exists in the code.
  Cite the commit/PR that fixed it.
- `STALE — CHANGED` — the surrounding code changed enough that the issue's
  approach/file references are wrong, even if the underlying problem may
  still exist. Say what's outdated.
- `OVERLAPS #N (partial|full)` — another issue or PR already covers part or
  all of it. Name the other issue/PR and which part it covers.

## Output format

A short table: `# | title | verdict | evidence (1 line: commit/PR/file)`.
Do not silently close or comment on issues — report findings and let Mario
decide whether to close, re-scope, or leave them.

## Common mistakes

- Trusting the issue title without reading the current file — code moves.
- Treating "a PR touched this file" as "this issue is fixed" without
  checking the PR actually addresses the described symptom.
- Skipping the board/label filter and auditing everything — this skill is
  for the pre-triaged approved+unassigned backlog, not full issue sweep.
