---
name: courier-health
description: Classify courier-integration errors in colete-online platform Loki logs by courier (FanCourier, DragonStar, GLS, UPS, Sameday, Cargus) and error class (HTTP/network, parse, application). Use when the user asks "how is FanCourier behaving", "which courier is broken", "are couriers healthy", "any DragonStar errors", "Sameday timeouts", or wants a courier-integration health check. Helpful when orders are failing and you need to know which carrier is the culprit.
allowed-tools: Bash(python3:*) Read
---

# courier-health — per-courier error classification

Aggregates courier-integration log lines over a window, classifies them by
courier (FanCourier, DragonStar, GLS, UPS, Sameday, Cargus) and error
class (network/timeout, parse, HTTP non-2xx, application), and ranks.

## When to use

- "Which courier is failing right now?"
- "Are FanCourier requests OK?"
- "DragonStar timeouts in the last hour?"
- "Why are orders stuck — courier issue?"

## How to run

```bash
python3 .claude/skills/courier-health/courier_health.py --since 24h
```

Flags:
- `--since 24h` — window (default `24h`).
- `--courier NAME` — restrict to one courier (e.g. `fan`, `dragon`,
  `sameday`). Substring match on internal courier names.
- `--samples 2` — sample lines per (courier, class) cell.
- `--addr URL` — Loki URL.

## What it returns

A matrix `courier × error_class` with counts, plus a representative line
per non-zero cell:

```text
courier        network  parse   http_4xx  http_5xx  app_error  total
FanCourier         0      6         0         0         32         38
DragonStar        20      0         0         0          0         20
GLS                0      0         0         2          0          2
...
```

Followed by samples for the loudest cells.

## Couriers and their log signatures

The script classifies on these substrings (case-insensitive):

| Courier    | Patterns                              |
|------------|---------------------------------------|
| FanCourier | `FanCourier`, `fan_courier`, `courier_fan_` |
| DragonStar | `DragonStar`, `dragonstar`            |
| GLS        | `GLS ERROR`, `\\bGLS\\b` (word-boundary) |
| UPS        | `UPS GET`, `UPS POST`, `\\bUPS\\b`    |
| Sameday    | `sameday`, `Sameday`                  |
| Cargus     | `cargus`, `Cargus`                    |

Error classes:
- **network**: `socket hang up`, `ECONNRESET`, `ETIMEDOUT`,
  `ECONNREFUSED`, `Request timed out`.
- **parse**: `Unexpected token`, `not valid JSON`, `<?xml`.
- **http_4xx**: `status code 4`, `HTTP 4`.
- **http_5xx**: `status code 5`, `HTTP 5`.
- **app_error**: anything else that mentioned the courier in an
  error- or warn-level line (the script pre-filters to those two
  levels, so info/verbose lines that happen to mention the courier
  in an unrelated payload don't pollute the count).

## Reference: equivalent lokictl one-liners

```bash
# All FanCourier-touching error lines:
./scripts/lokictl grep --since 24h --limit 50 -B 0 -A 0 \
    --level error "FanCourier"

# DragonStar network errors specifically:
./scripts/lokictl grep --since 24h --limit 50 -B 0 -A 0 \
    "DragonStar.*(socket hang up|ECONNRESET|ETIMEDOUT)"
```
