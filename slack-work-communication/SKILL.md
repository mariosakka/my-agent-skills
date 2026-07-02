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
source ~/.my-agent-skills/slack-work-communication/config/channels.sh
# Now use: $SLACK_ZDEV_STATUS for #zdev-status
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
2. **Ask if missing** — if a required detail is absent, ask before drafting (see Missing Details)
3. **Draft** — compose all messages using the templates
4. **Confirm** — show all drafts in one block, ask "Trimit? (da / nu / modifică)"
5. **Send** — use Slack MCP tools after user approves

## Channel Routing

| Situation | Channel | DM Alex? |
|---|---|---|
| SOD | #zdev-status | No |
| EOD | #zdev-status | No |
| Late arrival | #zdev-status | No |
| Early departure (planned) | #zdev-status | Yes |
| Early departure (urgent) | #zdev-status | Yes |
| Long break | #zdev-status | No |
| Review ready | #zdev-general | No |
| Deploy | #zdev-general | No |
| Part-time schedule | #zdev-status | No |

## Message Templates

**SOD:** `Salut, sunt pe [task] azi`

**EOD:** `Inchid. Am terminat [X] / maine continui pe [Y]`
- If resuming same day: `Inchid momentan, mai revin diseara. Am terminat [X].`

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

Always use `channel_id`, never the channel name string.

For DM to Alex:
1. Call `slack_search_users` with query `alex`
2. If multiple results: ask user "Care Alex?" and wait before sending
3. Call `slack_send_message` with channel set to Alex's user ID

## Missing Details

Ask before drafting if the required info is absent:
- **SOD / EOD**: no task mentioned → ask "Pe ce task esti / ai lucrat?"
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
