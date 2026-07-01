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

Manages two persistent work logs via shell scripts. Use `~/.desk/daily-log` for EOD, `~/.desk/weekly-log` for the Friday weekly message.

## Script interface

Both scripts have an identical interface:

    ~/.desk/daily-log add <section> "<text>"    # section: focus | blockers | help
    ~/.desk/daily-log remove <section> <N>      # N is 1-based
    ~/.desk/daily-log show                      # print formatted Slack message
    ~/.desk/daily-log clear                     # wipe all entries

(Replace `daily-log` with `weekly-log` for the weekly log.)

## Section mapping

| User describes | Section arg |
|---|---|
| Work done, PRs reviewed, tasks completed | `focus` |
| Something blocking progress | `blockers` |
| Help needed from someone | `help` |

## Which script to use

| Situation | Script |
|---|---|
| EOD | `~/.desk/daily-log` |
| Friday weekly report | `~/.desk/weekly-log` |
| Mid-week item worth noting for weekly | `~/.desk/weekly-log` |

## Rules

- NEVER edit `~/.desk/daily-log.json` or `~/.desk/weekly-log.json` directly
- Always run `show` before sending and present the output to the user for confirmation
- Run `~/.desk/daily-log clear` after the EOD message is confirmed sent
- Run `~/.desk/weekly-log clear` after the weekly message is confirmed sent

## EOD flow

1. Run `~/.desk/daily-log show`
2. Present output to user for review
3. Invoke `slack-work-communication` skill with the log output as the EOD message body
4. After user confirms send: run `~/.desk/daily-log clear`

## Weekly flow

1. Run `~/.desk/weekly-log show`
2. Present output to user for review
3. Invoke `slack-work-communication` skill with the log output as the weekly message body
4. After user confirms send: run `~/.desk/weekly-log clear`
