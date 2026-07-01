---
name: log-search
description: Search colete-online platform PRODUCTION logs (Loki) for arbitrary patterns, optionally restricted to a service, level, or time window. Use whenever the user wants to find specific log lines in production — "search the production logs for X", "grep prod logs for Y", "find lines containing Z in prod", "what's in production logs about Q", "any prod warnings about R", "show me prod logs from <service>", "what was <service> logging at <time>", "any warn lines about S today". Also use when the user says "search the logs" or "grep the logs" without explicitly naming an environment — in this codebase that means production. This is the generic search tool. Prefer this over `incident-trace` (which is identifier-focused), `error-overview` (aggregated summary), `courier-health` (courier-specific), and `service-restart-health` (crash/restart-specific). When the user wants raw log lines matching a pattern, use this skill. Do NOT use this for local dev-server output or files on disk — only the production Loki fleet.
allowed-tools: Bash(lokictl:*) Bash(./scripts/lokictl:*) Read
---

# log-search — generic production-log search

For when the user wants raw log lines matching a pattern, not an
aggregation or report. Wraps `lokictl grep` against the colete-online
production Loki instance.

> **Scope**: this skill searches **production** logs only — the Loki
> fleet that aggregates all swarm services. It does *not* search local
> `npm run start:dev` terminal output, files in `/var/log`, or any
> on-disk logs. If the user wants to grep their local dev server
> output, that's a different tool (and probably just `grep` against
> their terminal scrollback).

## When to use this skill (vs. siblings)

| User asks…                                          | Use                       |
|-----------------------------------------------------|---------------------------|
| "search for `ECONNREFUSED` in queue-courier"        | **this skill**            |
| "what was orders-updater logging at 14:32?"         | **this skill**            |
| "any warn lines about Sameday today?"               | **this skill**            |
| "trace order BBOI09SWSPSY"                          | `incident-trace`          |
| "what's broken in prod?" / "any errors today?"      | `error-overview`          |
| "is FanCourier failing?"                            | `courier-health`          |
| "is anything restarting?"                           | `service-restart-health`  |

Use this skill when the user wants **specific lines matching a specific
pattern**. If they have one identifier and want the whole story across
services, switch to `incident-trace`. If they want a summary instead of
lines, switch to `error-overview`.

## Finding lokictl

Try in this order:

1. `lokictl` on PATH (the common install).
2. The cached absolute path at `.claude/skills/_lokictl/.path`
   — sibling skills (incident-trace, courier-health, etc.) populate
   this on first successful discovery, so it's usually present.
3. `./scripts/lokictl` if the CWD is inside a colete-online checkout.

If none resolve, ask the user to install it once:
`ln -sf <repo>/scripts/lokictl ~/.local/bin/lokictl`.

## Invocation

```bash
lokictl grep [--service NAME] [--level LEVELS] [--since DUR]
             [-B N -A N] [-p] [-i] [--limit N] PATTERN [SELECTOR]
```

Most-used flags:

- `--service NAME` — substring match on swarm_service
  (e.g. `--service queue-courier`).
- `--level error,warn` — filter on the JSON `level` field;
  comma-separate for OR.
- `--since 1h` — window (`s`/`m`/`h`/`d`; default 1h). Anything past
  `7d` will be slow.
- `--until 30m` — window end, relative to now (default `0s`, i.e. now).
  Useful for "what happened around T" — set both `--since` and `--until`.
- `-B N -A N` — lines of context before/after each match (default 2).
  Pass `-B 0 -A 0` when you just want matches.
- `-p` / `--pretty` — pretty-print Winston-style JSON in lines.
- `-i` — case-insensitive.
- `--limit N` — max matches (default 1000).

Pattern is a Loki RE2 regex. Empty filter: pass `.` (matches every line).

For a stream selector beyond `--service`, append a LogQL selector as
the optional second positional, e.g. `'{swarm_service="exact-name"}'`.

## Examples

```bash
# All ECONNREFUSED in the last hour, anywhere
lokictl grep "ECONNREFUSED"

# Errors + warnings in one service, matches only (no context)
lokictl grep --service queue-courier --level error,warn -B 0 -A 0 "."

# One specific error pattern, pretty-printed, with 5 lines of context
lokictl grep --since 24h -p -C 5 "FanCourier GET Error"

# Exact stream selector (skip the --service substring shorthand)
lokictl grep --since 6h "timeout" '{swarm_service="co-back-fleet_orders-updater"}'

# "What was service X logging between 1h and 2h ago" — narrow the window
lokictl grep --service shipping-points --since 2h --until 1h "."
```

## Output

Default is human-readable: per-stream headers (`==> swarm_service=… <==`),
match lines marked with `*`, context lines dimmed. Pass `--json` for
JSONL (one object per line: `{ts_ns, labels, line, match}`) if you
need to post-process.

## Common pitfalls

- **Too-wide window + cheap pattern** = thousands of matches and a slow
  query. Start narrow (`--since 1h`) and widen if needed.
- **Substring vs. exact service**: `--service api` matches every service
  containing "api" (queue-api, api-server, …). For exact, use a full
  selector: `'{swarm_service="co-back-fleet_api-server"}'`.
- **Level filter is JSON-aware**: `--level error` looks for
  `"level":"error"` in the line. A line whose *message text* starts with
  "ERROR:" but whose JSON level is "warn" will NOT match. That's
  intentional — it filters on the structured level, not on the prose.
