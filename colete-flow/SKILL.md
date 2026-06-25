---
name: colete-flow
description: >-
  Standing workflow for any real task under ~/work on Colete Online repos
  (platform, magento_dev, prestashop-module, woocommerce-plugin, and any other
  ~/work repo tied to Colete Online). Invoke whenever Mario asks for actual work —
  a change, fix, feature, or investigation that will lead to a code change.
  Covers the Colete Online Standards Doc as it applies to Mario: GitHub issue
  creation and lifecycle (via co-ops skills); the >8h alignment gate; picking
  work off the GitHub Projects board; commit/push policy; the AI review loop on
  draft PRs; SOD/EOD/weekly Slack status (via the slack-work-communication skill).
  GitHub issues + the Projects board are the source of truth. There is NO Jira.
  NOT for pure questions or read-only exploration.
triggers:
  - starting a new task
  - picking up a task
  - creating an issue
  - alignment on a task
  - opening a PR
  - review loop
  - fixing review comments
  - deploying a task
  - weekly status
agents: all
version: 1
---

# colete-flow — how I work on Colete Online repos

The source of truth is the **GitHub issue** and the **GitHub Projects board**
(To Do → In Progress → In Review → Done, moved automatically). There is **no Jira**.

## When this applies

- Any **actual work** under `~/work` on Colete Online repos: a change, fix,
  feature, or investigation that will turn into a code change.
- **Don't** trigger for pure questions, explanations, or read-only exploration
  that will not produce a code change.

## Language

- **Slack → Romanian.** Use the `slack-work-communication` skill for all Slack
  messages — it has the templates, channel routing, and send gate.
- **Everything technical → English:** issues, commit messages, branch names,
  PR titles and descriptions, code, code comments.

## Hard rules (never violate)

- **I NEVER open a PR.** When the change is tested locally and the AI review is
  clean, I tell Mario "gata de PR"; **Mario opens the draft PR himself** (starts
  as draft, auto-linked to the issue). I then run the AI review loop on that
  draft.
- **I do NOT mark a PR "Ready for review."** That is Mario's gate — it triggers
  human-reviewer assignment. I only get the draft clean and tell him it's ready.
- **Commits/push: only when Mario asks, or inside a confirmed AI-review fix
  cycle.** The `gh` CLI is logged in as `PRCreatorNR1` (the shared PR account).
  I never push on my own initiative.
- **`approved` (which boards the issue) only on a stated Alex ok — never on my
  own judgment.** I apply `approved` + leave an attribution comment ("ok de la
  Alex, discutat in standup") **only when Mario tells me the ok exists.**
- **Human-in-the-loop gates are real waits.** Where this skill says "wait for
  confirmation", I stop and wait — I do not assume.
- **Outward-facing sends need an OK.** All Slack messages are drafted, shown to
  Mario, and sent only after his approval (via the `slack-work-communication`
  skill).
- **Never read production or shared env files; never touch production data.**
  In `platform`, never read `.env.development` or any shared/prod env files —
  listing file *names* is fine, reading contents is not. `.env.local` is OK.
  Any DB/data change runs only against the local environment.
- **Prisma commands are never run automatically.** Always suggest them for
  manual execution (`prisma migrate`, `prisma generate`, `prisma db push`).
- **Never blanket-stage.** Always `git add <explicit file paths>`. Never
  `git add -A`, `git add .`, or `git commit -am`. Before every push, run
  `git show --stat HEAD` and confirm the file list matches exactly what was
  intended.

## Slack channels (reference only — use the slack-work-communication skill to send)

- **#zdev-status** — SOD/EOD, long breaks, early leave, late start, situations.
- **#zdev-general** — daily coordination, "gata de review" announcements.
- **#zdev-pulse** — task threads (>1 day) + automated review signals. Most arrive
  via the GitHub↔Slack integration — don't double-post.
- **#zdev-weekly** — weekly status (Focus / Blocaje / Ajutor necesar), by Fri 15:00,
  as a new message (not a thread reply). All tasks as `#N titlu`.
- **#zdev-deploy** — production deploy announcements + post-deploy verification.

## Tooling — co-ops skills

Install once: `/plugin marketplace add Colete-Online/ai-tooling` then
`/plugin install co-ops@ai-tooling`.

- **co-ops:issue-creation** — file a structured issue (team template + machine-read
  `Estimation:` line). Never boards, approves, or assigns.
- **co-ops:issue-alignment** — write the §5 alignment comment for a >8h issue.
- **co-ops:issue-alignment-check** — self-check the alignment comment before
  labeling `alignment-ready`.
- **co-ops:pr-merge-check** — on a draft PR: "is it ready to mark Ready for review?"

## The flow

### 1. A new idea / bug / regression → an issue

Create with **co-ops:issue-creation**. It lives in the repo backlog; it does NOT go
on the board until Alex applies `approved`. I never apply `approved` myself.
For new ideas Mario drops, I file them as issues rather than only remembering them.

### 2. Picking up a task

- From the **top 3 unassigned** issues in To Do (or one Alex assigns directly).
- **≤8h:** Mario can start directly. If it grows past a day once in the code,
  post the alignment comment retroactively (just the new estimate).
- **>8h:** exploration (2–4h) → alignment comment via **co-ops:issue-alignment**
  → **co-ops:issue-alignment-check** → apply label `alignment-ready` → **wait for
  Alex's confirmation** (that is the start ok) → only then move to In Progress and
  write real code. Probe code to validate an approach is fine; full implementation
  on an unconfirmed approach is not.
- Overruns (>50% past estimate, or >1 day): post the new estimate on the issue
  the same day we realize it — no justifications on the spot, those come at close.

### 3. Branch and worktree

All feature and bugfix branches start from `development` (not `main`):

```bash
git checkout development && git pull origin development
git checkout -b feature/your-feature-name
```

In `platform`, work in an isolated git worktree when the change touches multiple
unrelated areas. `node_modules`, env files, and generated config are per-worktree.

### 4. Doing the work

- I push commits when Mario asks (or inside a confirmed AI-review fix cycle).
- `gh` CLI is logged in as `PRCreatorNR1` (the shared PR account). Commits and
  pushes go through this account. Mario's personal account is `mariosakka`.
- Off-issue work Mario flags explicitly ("azi am mai facut si asta") gets a one-line
  note so it's not lost for the weekly status.

### 5. PR + AI review loop (I drive; I don't open or "ready" the PR)

1. When the change is **tested locally** and CI/linting is clean, I tell Mario
   "gata de PR"; he opens the **draft PR** from the `PRCreatorNR1` shared account
   and confirms it's open. I then assign the issue to `mariosakka` (his personal
   account) — this is mandatory since the PR comes from the shared account; the
   issue assignee is how the team identifies the real author.
2. On the draft I run the AI review: `/review`, `/simplify`,
   and **co-ops:pr-merge-check**. Issue stays In Progress; no human yet.
3. I read every review comment and classify each:
   **valid** (real, worth doing — one-line why) / **invalid** (wrong or out of scope
   — one-line why). I present the full list to Mario.
4. I **wait** for Mario's valid/invalid confirmation.
5. Per thread: **invalid** → reply briefly why not + resolve; **valid** → reply
   "facem" → make the change → push → resolve. Re-wait for the next review round;
   repeat until clean.
6. When clean, CI is green, and self-review notes are on anything non-obvious,
   I tell Mario **"gata de Ready for review"** — he marks it ready (his gate).
   I never mark it ready myself.

### 6. After ready: human review → merge → deploy → verify

Automation assigns the human reviewer and posts to #zdev-pulse — I don't pick a
reviewer or announce manually. On requested changes: fix + reply per thread + ask
for re-review. Approve → `ready-to-merge` → **Alex merges + deploys** (announced
in #zdev-deploy). After the deploy announcement, I help Mario run the PR's
"How to test" steps against prod and tick the deploy message. If something breaks:
reopen the issue and write the 3-line regression note (what happened / why / what
we do next).

## Proactive guardrails (I flag when Mario is about to break the doc)

I speak up if:
- A >8h task is starting without a confirmed alignment.
- An issue would go on the board without `approved`.
- A PR is heading to "Ready for review" without green CI / AI review / self-review.
- A task is being pulled from outside the top 3 of To Do (unless Alex assigned it).
- An estimate is >50% over without a posted update on the issue.
- A PR mixes unrelated changes.
- SOD/EOD or the Friday weekly is missing while we're active.

## Quick reference

- GitHub: `gh` CLI logged in as `PRCreatorNR1` (shared PR account, ssh).
  Mario's personal account: `mariosakka` — used for issue assignment only.
- Issues / alignment / PR-readiness: the **co-ops** skills.
- Slack messages: the **slack-work-communication** skill — always draft, show,
  send on Mario's OK.
- Branches always from `development`.
- No Jira anywhere.
- Prisma: never run automatically, always suggest for manual execution.
