---
name: log-triage
description: Survey what's broken in the colete-online platform Loki logs over the last N hours. Aggregates error-level lines by swarm_service, clusters by message signature, and returns a ranked summary with one representative line per group. Use whenever the user asks "what's broken", "what's failing", "any errors today", "log triage", "anything wrong in prod", "morning health check", or wants a 24h log overview. Reads from the internal Loki instance (default http://10.10.0.190:3100); no project repo required.
allowed-tools: Bash(python3:*) Read
---

# log-triage — "what's broken in prod?"

Produces a triage report for the colete-online platform from Loki logs.
Reads from the internal Loki instance (default `http://10.10.0.190:3100`,
override with `LOKI_ADDR`).

## When to use

- "What's broken in the last 24h?"
- "Any errors today?"
- "Triage the prod logs"
- "Anything failing on the back fleet?"
- Periodic morning health-check.

## How to run

The skill ships with a helper script. From the project root:

```bash
python3 .claude/skills/log-triage/triage.py --since 24h
```

Flags:
- `--since 24h` — window (default `24h`; supports `s`/`m`/`h`/`d`).
- `--top 8` — how many top services to detail (default 8).
- `--samples 3` — sample lines per signature group (default 3).
- `--service NAME` — restrict to one swarm_service substring.
- `--addr URL` — override Loki base URL.

## What it returns

1. **Per-service error count** — sum over the window, ranked.
2. **Top message signatures** — first ~80 chars of the JSON `message` field
   with digit runs and quoted IDs collapsed to `*`, so repeat errors cluster.
3. **One sample line per signature** — full raw line for the first hit.

## How to read the output

- Signatures with high counts and one host: localized bug, look at the
  service code first.
- Signatures with high counts and many hosts: shared dependency
  (database, courier API, queue) — check for upstream incident first.
- An error class that wasn't in yesterday's run is the interesting one.
  This skill doesn't diff runs — eyeball it.

## Reference: equivalent lokictl one-liners

If the helper script is missing or you want to drill into one signature:

```bash
# Top-N error sample for a single service (no context fetch — fast):
./scripts/lokictl grep --since 24h --limit 50 -B 0 -A 0 \
    --level error --service invoicing-system "."

# Pretty-print a sample of one signature:
./scripts/lokictl grep --since 24h --limit 5 -p \
    --level error "Field 'zip_file_path' doesn't have"
```

## Known noise

- `co-api-fleet_api-server` warns whose message string starts with
  `ERROR: /validate-postal-code/...` — these are `level":"warn"`, not
  errors. The `--level error` filter excludes them.
- `co-back-fleet_orders-updater` `DragonStar GET error: socket hang up`
  is recurring upstream flakiness, not a code bug.
