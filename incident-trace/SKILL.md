---
name: incident-trace
description: Render a unified time-ordered timeline of all colete-online platform Loki log lines that match an identifier (trace_id, order_id, AWB, userId, email, x-trace-id). Use when the user pastes an identifier and asks "what happened with order X", "trace this", "follow this trace_id", "logs for AWB Y", "where did this user fail", "give me a timeline for", or wants to debug a single incident across services. Runs against the colete-online Loki instance.
allowed-tools: Bash(python3:*) Read
---

# incident-trace — single-incident timeline

Pulls every Loki log line matching an identifier across all services, sorts
by timestamp, and prints one line per event so you can read the incident
top-to-bottom regardless of which service emitted what.

## When to use

- "Trace `b42477c2ee39d563c8d48b25dca395f4`"
- "What happened with order BBOI09SWSPSY?"
- "Follow AWB 1ONBLN493122394"
- "Why did user 190220 fail at checkout?"
- Any time the user has *one* identifier and wants the full picture
  across services.

## How to run

```bash
python3 .claude/skills/incident-trace/trace.py "<identifier>" --since 24h
```

Flags:
- `--since 24h` — search window (default `24h`).
- `--limit 1000` — max lines per stream (default 1000).
- `--addr URL` — override Loki base URL.
- `--pretty` — unwrap Winston-style JSON in lines.
- `--service NAME` — restrict to a swarm_service substring.

## What it returns

A single chronological timeline:

```text
HH:MM:SS.mmm  [swarm_service]  <line excerpt>
```

Lines are sorted globally — across services — so request → queue → courier
→ email handoffs read in causal order. Long lines are truncated to 240
chars by default; use `--full` to see raw lines.

## Identifier handling

The script greps Loki for the literal identifier — no smart parsing. If the
identifier contains regex metacharacters (slashes, dots), they're escaped
automatically. UUIDs, AWB strings, order codes, numeric IDs, and email
addresses all work as-is.

If you want OR-matching across multiple identifiers, pass them
comma-separated: `"id1,id2,id3"`.

## Reference: equivalent lokictl call

```bash
./scripts/lokictl grep --since 24h --limit 500 -B 0 -A 0 -p "<identifier>"
```

This produces per-stream output. The skill's helper merges streams into a
single timeline, which is what you almost always want for incident review.
