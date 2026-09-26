---
name: pr-audit
description: >-
  Audit Mario's own in-flight GitHub pull requests: PRs he's assigned to
  (or backing an issue assigned to him) that aren't merged yet — draft or
  ready, reviewed or not, reviewers assigned or not, or bounced back to
  draft after being ready — and separately, PRs where he's a requested
  reviewer and hasn't reviewed yet. Use when Mario asks "what PRs am I
  supposed to review", "check my open PRs", "which of my PRs need a
  review", "any PRs stuck in draft", "did my PR get put back into draft",
  "what's waiting on me", or before a standup/EOD status update. NOT for
  judging whether a PR is safe to merge (use co-ops:pr-merge-check) or for
  a general code review of PR contents.
triggers:
  - my open PRs
  - PRs assigned to me
  - PRs I need to review
  - review requested
  - PR put back into draft
  - what's waiting on me
agents: all
version: 1
---

# pr-audit — status of Mario's in-flight PRs

Splits into a **deterministic fetch** (script, no LLM judgment) and a short
**agent read-out** (you summarize/prioritize what the script found — no
extra GitHub calls needed for the common case). Never eyeball the PR list
in the UI/memory instead of running the script — reviewer/draft state
changes constantly and must come from a live query.

**Why assignee, not author:** in Colete-Online/platform (and similar repos
using the `gh-pr` shared-account workflow), PRs are opened from shared/bot
accounts (`PRCreatorNR1`, `Devify101`, ...), never Mario's own login. The
`author` field is therefore useless for "is this my PR" — the signal is
the PR **assignee**, or (if unassigned on the PR itself) the assignee of
the issue the PR closes.

## Phase 1 — Fetch (script only)

```bash
# PRs that are "mine": I'm the PR assignee, or assigned to its closing issue
scripts/fetch-pr-audit.sh --mode authored --repo OWNER/REPO --out /tmp/authored.json

# PRs where I'm a requested reviewer and haven't reviewed yet
scripts/fetch-pr-audit.sh --mode to-review --repo OWNER/REPO --out /tmp/to-review.json
```

`--user LOGIN` overrides the default (the authenticated `gh` user). Run
`--help` for details.

**`authored` output per PR:** `number`, `title`, `url`, `isDraft`,
`createdAt`, `updatedAt`, `reviewersRequested` (still-pending logins),
`humanReviews` (non-bot reviews, excluding the user's own), `botReviews`
(e.g. coderabbitai), `wasPutBackToDraft` (true if a
`CONVERT_TO_DRAFT_EVENT` ever fired — only possible if it had been Ready
for review at some point).

**`to-review` output per PR:** `number`, `title`, `url`, `author`,
`isDraft`, `reviewersRequested`, `reviewsAlreadyReceived` (what others have
already said, for context/priority).

## Phase 2 — Read out (agent)

No code-reading is required for the common case — this is a status query
over GitHub metadata, not a code audit. Group `authored` results into:

- **Needs reviewers** — `reviewersRequested` empty AND `humanReviews`
  empty AND not draft. Nobody is going to look at this unless someone gets
  requested.
- **Awaiting review** — `reviewersRequested` non-empty, no `humanReviews`
  yet.
- **Reviewed, no verdict shown** / **has human review(s)** — list the
  reviewer and state (`APPROVED`/`CHANGES_REQUESTED`/`COMMENTED`).
- **Bounced back to draft** — `wasPutBackToDraft: true`. Flag regardless
  of current draft state; if `isDraft` is still true, say so explicitly
  ("currently draft, was ready before").
- **Still draft, never was ready** — `isDraft: true`, `wasPutBackToDraft: false`.

For `to-review`, just list them — these are already filtered to "pending
on me"; report title, author, and whether other reviewers have already
weighed in (useful to gauge urgency/agreement before you look).

**If a claim needs current code, not just PR metadata** (e.g. "is this
review comment still valid given the diff"): `git fetch origin` first and
diff against `origin/<default-branch>`, not a possibly-stale local
checkout — same rule as `issue-audit`.

## Output format

Two short tables, one per mode: `# | title | draft? | reviewers requested |
reviews so far | notes (bounced-to-draft, etc.)`. Don't silently ping
reviewers, re-request review, or change draft status — report and let
Mario act.

## Common mistakes

- Filtering by `author.login == Mario` — wrong in shared-account repos,
  silently returns zero PRs. Use assignee (PR or backing issue).
- Treating a bot review (coderabbitai) as satisfying "has this been
  reviewed" when the user means human sign-off — report bot and human
  reviews separately, let the human-review count answer that question.
- Missing a "bounced to draft" PR because it's currently Ready again —
  `wasPutBackToDraft` is about history, not current state.
