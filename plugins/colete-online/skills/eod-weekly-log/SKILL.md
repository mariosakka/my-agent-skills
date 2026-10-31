---
name: eod-weekly-log
description: >-
  Manages EOD and weekly work logs via scripts. Add items to daily or weekly
  log, show formatted Slack output, clear after send. Use when the user wants
  to log something they did, asks for EOD/weekly status, or is about to send
  an EOD or weekly Slack message. Never edits JSON files directly.
triggers:
  - end of day
  - EOD
  - weekly report
  - log what I did
  - add to focus
  - note a blocker
  - help needed
agents: all
version: 1
---

# eod-weekly-log

Manages two persistent work logs via shell scripts. Use `~/.desk/daily-log` for EOD, `~/.desk/weekly-log` for the Friday weekly message. Scripts live in the skill's base directory (the folder containing this SKILL.md) (symlinked into `~/.desk/`). JSON data is stored in `~/.local/share/desk-logs/`.

## Script interface

Both scripts have an identical interface:

    ~/.desk/daily-log add <section> "<text>"    # section: focus | blockers | help
    ~/.desk/daily-log remove <section> <N>      # N is 1-based
    ~/.desk/daily-log show                      # print formatted Slack message
    ~/.desk/daily-log clear                     # wipe all entries

(Replace `daily-log` with `weekly-log` for the weekly log.)

## Language — Romanian only

All log entry text (focus, blockers, help) must be written in **Romanian, no diacritics** — this matches how the logs get read out in Slack. Never write entries in English; if the user describes work in English, translate it into Romanian before calling `add`. Links, PR/issue numbers, and technical identifiers (file paths, function names) stay as-is — only the surrounding prose is Romanian.

## Section mapping

| User describes | Section arg |
|---|---|
| Work done, PRs reviewed, tasks completed | `focus` |
| Something blocking progress | `blockers` |
| Help needed from someone | `help` |

## Adding focus items — links are mandatory whenever one exists

Every **focus** item that references a PR, issue, or commit must include its link. This is not optional — a focus entry naming a PR/issue number without the matching URL is incomplete.

- If the user gives a PR/issue number without a link, look it up yourself first (e.g. `gh pr view <N> --repo <owner>/<repo> --json url -q .url` / `gh issue view <N> ...`) before adding the entry — don't just ask the user for it.
- If you can't resolve a link automatically (wrong repo, ambiguous number, or genuinely no PR/issue/commit behind the item — e.g. "research pe partea de retururi"), ask: "Ai un link asociat? (PR, Issue, etc.)" — and if there truly isn't one, add the text as-is without a link.
- Append the link at the end of the text — e.g. `"Reviewed PR #123 — fixed auth bug https://github.com/org/repo/pull/123"`. If an entry references more than one PR/issue, append all relevant links.

Do not ask for links on `blockers` or `help` items (they normally don't reference a PR/issue).

## Logging a completed item — ALWAYS add to BOTH logs

When you log something the user **did** (a `focus` item — a PR, fix, review, task completed), you MUST add it to **both** the daily log AND the weekly log, in the same turn. Not one or the other — both. A completed item belongs in today's EOD *and* accumulates toward the Friday weekly, so run the `add` twice:

    ~/.desk/daily-log  add focus "<text>"
    ~/.desk/weekly-log add focus "<text>"

This is mandatory and easy to forget — if you added a focus item to only one log, you are not done. The only exceptions:

- The user explicitly scopes it to one log ("just the weekly", "only EOD").
- `blockers` / `help` items — these are transient day-state, so they go to the **daily log only** unless the user says otherwise.

## Which script to use

| Situation | Script |
|---|---|
| A completed item (focus) | **BOTH** `~/.desk/daily-log` and `~/.desk/weekly-log` |
| A blocker / help-needed | `~/.desk/daily-log` only |
| EOD send | `~/.desk/daily-log` |
| Friday weekly send | `~/.desk/weekly-log` |

## Rules

- A completed (`focus`) item goes to **both** logs — see "Logging a completed item". Adding it to only one is a bug.
- NEVER edit `~/.local/share/desk-logs/daily-log.json` or `~/.local/share/desk-logs/weekly-log.json` directly
- Always run `show` before sending and present the output to the user for confirmation
- Run `~/.desk/daily-log clear` after the EOD message is confirmed sent
- Run `~/.desk/weekly-log clear` after the weekly message is confirmed sent

## EOD flow

1. Run `~/.desk/daily-log show`
2. **Before sending:** confirm the log is non-empty — if output is blank or whitespace only, ask the user what to include rather than sending a blank message.
3. Present output to user for review
4. Invoke `slack-work-communication` skill with the log output as the EOD message body
5. After user confirms send: run `~/.desk/daily-log clear`

## Weekly flow

1. Run `~/.desk/weekly-log show`
2. Present output to user for review
3. Invoke `slack-work-communication` skill with the log output as the weekly message body
4. After user confirms send: run `~/.desk/weekly-log clear`
