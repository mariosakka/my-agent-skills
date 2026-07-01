---
name: service-restart-health
description: Detect crashing or restarting services in the colete-online platform by counting RabbitMQ-connect startup banners, uncaughtException, unhandledRejection, and OOM (JavaScript heap out of memory / FATAL ERROR) per swarm_service over a window. Use when the user asks "is anything crashing", "service restarts", "are services healthy", "any OOM", "memory leak", "process death", "any unhandled rejections", or wants a process-stability check. Flags services over a restart threshold and pulls the last lines before each restart so you can see what the process was doing when it died.
allowed-tools: Bash(python3:*) Read
---

# service-restart-health — process stability audit

Counts process-death and restart signals across the platform's services
over a window and ranks the worst offenders.

## When to use

- "Is anything restarting in prod?"
- "Any services crashing today?"
- "Any out-of-memory kills?"
- "Did `queue-emails-server` get restarted?"
- Periodic morning stability check.

## How to run

```bash
python3 .claude/skills/service-restart-health/restart_health.py --since 24h
```

Flags:
- `--since 24h` — window (default `24h`).
- `--threshold 3` — flag services with strictly more restarts than this
  (default 3, just above the typical deploy floor — see caveats below).
- `--by-host` — break down per `host` instead of `swarm_service` (useful
  when you suspect one Swarm node is flapping).
- `--samples 5` — for flagged services, lines preceding each restart.
- `--addr URL` — Loki URL.

## What it returns

A per-service table with four columns plus a flag column:

```
swarm_service                          restarts  uncaught  unhandled  OOM
co-front-fleet_queue-emails-server         15        12         0      0   ⚠
co-front-fleet_queue-courier-1             13         3         0      0   ⚠
co-back-fleet_orders-updater                4         0         0      1   ⚠
co-back-fleet_admin-dashboard-server        1         0         0      0
...
```

For each ⚠-flagged service, the script then prints the last N log lines
preceding the most recent restart (or restart cluster) so you can see
what the process was doing when it died.

## Restart-detection caveats

- **Restart count is a proxy.** Each colete-online service prints
  `Successfully connected to RabbitMQ` once at boot, so we count those
  banners. Services without RabbitMQ (a few HTTP-only servers) instead
  print `listening on port` — both are matched.
- **Clean redeploys also fire the banner.** Swarm rolling-updates show
  up as "restarts" — typically exactly 3 per service per deploy (one
  per replica). The default `--threshold 3` puts deploys below the
  flag line; only services flapping above that level (4+) get ⚠.
  If you suspect a deploy distorted today's numbers, narrow the
  window with `--since 2h` so the deploy falls outside it.
- **Silent OOM kills don't always log a stack.** Node v24's
  `--heap-prof` settings vary; some OOMs print the FATAL line, some
  just exit and only the *next* boot's banner is visible. Cross-check
  with the `OOM` column.

## What 0 unhandledRejection means

In the colete-online services, this is usually 0 because the process is
configured to upgrade unhandled rejections to `uncaughtException` (look
for `process.on("unhandledRejection", …)` in the bootstrap files). The
column is kept so a non-zero number stands out as a config regression.

## Reference: equivalent lokictl one-liners

```bash
# Restart banner count per service:
./scripts/lokictl grep --since 24h --limit 500 -B 0 -A 0 \
    "Successfully connected to RabbitMQ"

# OOM hits:
./scripts/lokictl grep --since 24h --limit 50 -B 0 -A 0 \
    "JavaScript heap out of memory|FATAL ERROR.*Allocation"
```
