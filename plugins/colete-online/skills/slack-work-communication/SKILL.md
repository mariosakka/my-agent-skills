---
name: slack-work-communication
description: >
  Use for ANY Slack work status communication request. Trigger phrases include:
  "end of day", "EOD", "start of day", "SOD", "inchid", "incep", "put a message on slack",
  "send on slack", "announce on slack", "plec", "vin dupa", "pauza", "gata de review",
  "deploy", "leaving early", "working part-time". Do NOT wait for the user to name this
  skill explicitly — if they describe a work situation that needs a Slack message, invoke
  this skill immediately.
---

# Slack Work Communication

## Channel IDs

Channel IDs are stored in `config/channels.sh` — source it rather than hardcoding:

```bash
source <skill-dir>/config/channels.sh   # <skill-dir> = the directory containing this SKILL.md
# Now use: $SLACK_ZDEV_STATUS for #zdev-status, $SLACK_ZDEV_WEEKLY for #zdev-weekly
```

## Overview

Classify the user's work situation, compose the correct Slack messages per team standards, confirm with the user, then send via Slack MCP.

## When to Use

Activate when the user describes any of these:
- Starting or ending their workday (SOD / EOD)
- Arriving late (after 11:00)
- Leaving early (planned or urgent)
- Taking a long break (>30 min)
- A task being ready for review
- Deploying a task
- Announcing their part-time work schedule for the week

## Process

1. **Classify** — identify situation type from the routing table below
2. **Read log** — for EOD or weekly, run the appropriate log script to get content (see Log Integration)
3. **Ask if missing** — if a required detail is still absent after reading the log, ask (see Missing Details)
4. **Draft** — compose all messages using the templates
5. **Confirm** — show all drafts in one block, ask "Trimit? (da / nu / modifică)"
6. **Send** — use Slack MCP tools after user approves
7. **Clear log** — after confirmed send, clear the appropriate log (see Log Integration)

## Channel Routing

| Situation | Channel | DM Alex? |
|---|---|---|
| SOD | #zdev-status | No |
| EOD | #zdev-status | No |
| Weekly | #zdev-weekly | No |
| Late arrival | #zdev-status | No |
| Early departure (planned) | #zdev-status | Yes |
| Early departure (urgent) | #zdev-status | Yes |
| Long break | #zdev-status | No |
| Review ready | #zdev-general | No |
| Deploy | #zdev-general | No |
| Part-time schedule | #zdev-status | No |

EOD always goes to #zdev-status only — never merge it into or send it to #zdev-weekly. Weekly always goes to #zdev-weekly only — never #zdev-status.

## Log Integration

For EOD and weekly situations, always read from the log scripts before drafting — do not ask the user for content if the log is non-empty.

| Situation | Script | Clear after send |
|---|---|---|
| EOD | `~/.desk/daily-log show` | `~/.desk/daily-log clear` |
| Weekly | `~/.desk/weekly-log show` | `~/.desk/weekly-log clear` |

**Reading the log:**
```bash
~/.desk/daily-log show   # for EOD
~/.desk/weekly-log show  # for weekly
```

If the output is blank or contains only whitespace, fall back to asking the user what to include.

**Using the log output — EOD:**
- Extract only the focus bullet lines (lines starting with `•` between `:dart: Focus` and `:construction: Blocaje`).
- Do NOT include section headers (`:dart:`, `:construction:`, `:raising_hand:`) or the blocaje/ajutor sections.
- Format as:
  ```
  Inchid.
  • item 1
  • item 2
  ...
  ```

**Using the log output — Weekly:**
- Use the full output as-is (all sections: focus, blocaje, ajutor necesar).
- Do not prepend anything extra.

**Clearing after send:**
Run the clear command only after the user confirms with "da" and the message has been sent successfully:
```bash
~/.desk/daily-log clear   # after EOD sent
~/.desk/weekly-log clear  # after weekly sent
```

## Message Templates

**SOD:** `Salut, sunt pe [task] azi`

**EOD:**
```
Inchid.
• [focus item 1]
• [focus item 2]
...
```
Only focus items — no section headers, no blocaje, no ajutor necesar.
- If resuming same day: use `Inchid momentan, mai revin diseara.` instead of `Inchid.`

**Weekly:**
```
[full output of ~/.desk/weekly-log show — all sections as-is]
```

**Late arrival:** `Vin dupa [ora]`

**Early departure (planned):**
- #zdev-status: `Plec azi la [ora].`
- DM Alex: `Hey Alex, plec azi la [ora][— reason if provided].`

**Early departure (urgent):**
- #zdev-status: `Plec acum[, reason if provided].`
- DM Alex: `Hey Alex, plec acum[— reason if provided].`

**Long break:** `Pauza [start]–[end], revin dupa.`

**Review ready:** `Gata de review: [task name/link]`

**Deploy:** `Deploy [task name][— brief description if provided]`

**Part-time schedule:** `Saptamana asta lucrez: [days]`

## Confirmation Block

Always show this before sending anything:

```
📋 Mesaje de trimis:

[#zdev-status]
"[message text]"

[DM → alex]
"[message text]"

Trimit? (da / nu / modifică)
```

For weekly, the confirmation block header is `[#zdev-weekly]` instead of `[#zdev-status]`.

- **da** → send all messages via Slack MCP
- **nu** → cancel, send nothing
- **modifică [what]** → adjust that message, re-show confirmation block

## IMPORTANT: Always Confirm Before Sending

Never call `slack_send_message` without first showing the confirmation block and receiving "da" from the user. Even if the situation is obvious, always confirm.

## IMPORTANT: Never Use Slack Drafts

Never call `slack_send_message_draft`. All drafts must be shown as the confirmation block in the Claude session itself. The Slack draft feature is not to be used under any circumstances.

## IMPORTANT: DM Alex Is Mandatory for Departures

For both planned and urgent early departures, the DM to Alex is not optional — always include it in the confirmation block alongside the channel message.

## Sending via Slack MCP

Use the hardcoded channel IDs below — do NOT search for channels, searching returns results in unpredictable order and you will pick the wrong one:

| Channel | channel_id |
|---|---|
| #zdev-status | `C0B78TRCQDD` |
| #zdev-weekly | `C0B0A0C3MB2` |

Always use `channel_id`, never the channel name string.

For DM to Alex:
1. Call `slack_search_users` with query `alex`
2. If multiple results: ask user "Care Alex?" and wait before sending
3. Call `slack_send_message` with channel set to Alex's user ID

## Missing Details

Ask before drafting if the required info is absent:
- **SOD**: no task mentioned → ask "Pe ce task esti azi?"
- **EOD / Weekly**: log is empty → ask "Ce ai lucrat? (logul e gol)"
- **Any departure**: no time given → ask "La ce ora pleci?"
- **Long break**: no times given → ask "Intre ce ore e pauza?"

## Message Merging

When the user provides multiple situations in one request that would both post to the **same channel**, combine them into a **single message** — never send two separate messages to the same channel.

Common merge cases:
- **SOD + early departure** → one #zdev-status message: `Salut, sunt pe [task] azi. E posibil sa plec [mai devreme / la ora].`
- **SOD + late arrival** → one #zdev-status message: `Salut, vin dupa [ora], sunt pe [task].`
- **EOD + long break note** → one #zdev-status message combining both

The DM to Alex (for departures) is always a **separate** message — never merged with the channel post.

## Edge Cases

- **Resuming same day**: after EOD, user must post a new SOD when they resume
- **Part-time + holiday**: do not calculate recovery hours — just post the days the user provides
- **Long break + EOD**: note the adjusted EOD time in the break message if user provides enough info
