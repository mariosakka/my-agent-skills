#!/usr/bin/env python3
"""
service-restart-health helper — count restart banners, uncaughtException,
unhandledRejection and OOM markers per service over a window.

Implementation: shells out to `lokictl count` once per signal for the
per-service counts, then for each flagged service uses `lokictl grep`
twice: once to find the most recent restart banner timestamp, once to
fetch the 60s window of lines preceding it. The script owns the signal
taxonomy and the flag/threshold logic; lokictl owns the Loki calls.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# Shared lokictl discovery lives in a sibling _lokictl/ package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lokictl.find import find_lokictl  # noqa: E402


SIGNALS: list[tuple[str, str]] = [
    # (column_name, RE2 pattern for the Loki line filter)
    ("restarts",
     r"Successfully connected to RabbitMQ|listening on port"),
    ("uncaught",
     r"uncaughtException"),
    ("unhandled",
     r"unhandledRejection|UnhandledPromiseRejection"),
    ("OOM",
     r"JavaScript heap out of memory|FATAL ERROR.*Allocation"),
]


def run_lokictl(cmd: list[str]) -> str | None:
    """Return stdout, or None on timeout / non-zero exit.

    Silent failure here would look like "no restarts" — i.e. all green —
    which is exactly the wrong signal during a real outage. Returning
    None lets callers distinguish failure from a genuinely empty result.
    """
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              timeout=120)
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"warn: lokictl timed out: {' '.join(cmd)}\n")

        return None
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        sys.stderr.write(
            f"warn: lokictl exited {proc.returncode}: {' '.join(cmd)}"
            + (f"\n  {err}\n" if err else "\n"))

        return None

    return proc.stdout


def count_signal(lokictl: str, pattern: str, group_by: str,
                 since: str, addr: str | None) -> dict[str, int]:
    """Run `lokictl count --by <group_by> <pattern>` → {label: count}."""
    cmd = [lokictl, "count", "--by", group_by,
           "--since", since, "--json"]
    if addr:
        cmd.extend(["--addr", addr])
    cmd.append(pattern)

    out: dict[str, int] = {}
    raw_out = run_lokictl(cmd)
    if raw_out is None:
        return out
    for raw in raw_out.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        try:
            out[str(obj["value"])] = int(obj["count"])
        except (KeyError, TypeError, ValueError):
            continue

    return out


def fetch_lines(lokictl: str, group_by: str, label_value: str,
                pattern: str, since: str, until: str, limit: int,
                addr: str | None) -> list[tuple[int, str]]:
    """`lokictl grep PATTERN '{<group_by>="<value>"}'` → [(ts_ns, line)]."""
    # json.dumps handles quote/backslash escaping the way LogQL expects.
    selector = "{" + group_by + "=" + json.dumps(label_value) + "}"
    cmd = [lokictl, "grep", "--json",
           "--since", since,
           "--until", until,
           "--limit", str(limit),
           "-B", "0", "-A", "0"]
    if addr:
        cmd.extend(["--addr", addr])
    cmd.extend([pattern, selector])

    out: list[tuple[int, str]] = []
    raw_out = run_lokictl(cmd)
    if raw_out is None:
        return out
    for raw in raw_out.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        try:
            out.append((int(obj["ts_ns"]), str(obj["line"])))
        except (KeyError, TypeError, ValueError):
            continue
    out.sort()

    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="service-restart-health")
    p.add_argument("--since", default="24h",
                   help="window (default 24h)")
    p.add_argument("--threshold", type=int, default=3,
                   help="flag services with strictly more restarts "
                        "than this (default 3 — set above the typical "
                        "deploy floor; rolling Swarm deploys produce "
                        "exactly 3 banner hits per service)")
    p.add_argument("--by-host", action="store_true",
                   help="aggregate per host rather than swarm_service")
    p.add_argument("--samples", type=int, default=5,
                   help="lines preceding the latest restart for "
                        "flagged services (default 5)")
    p.add_argument("--addr",
                   help="Loki URL (passed to lokictl)")
    p.add_argument("--context-limit", type=int, default=200,
                   help="max lines per pre-restart context fetch "
                        "(default 200)")
    args = p.parse_args()

    lokictl = find_lokictl()
    group_by = "host" if args.by_host else "swarm_service"

    # Per-signal aggregation. Keep results independent so a partial
    # failure (one signal's query times out) still gives useful output.
    counts: dict[str, dict[str, int]] = {}
    for col, pat in SIGNALS:
        counts[col] = count_signal(lokictl, pat, group_by,
                                   args.since, args.addr)

    services = sorted(set().union(*(c.keys() for c in counts.values())))
    if not services:
        print(f"no signals in last {args.since}")

        return 0

    services.sort(key=lambda s: (
        -counts["restarts"].get(s, 0),
        -counts["uncaught"].get(s, 0),
    ))

    cols = [c for c, _ in SIGNALS]
    name_w = max(len(s) for s in services)
    print(f"## process-stability per {group_by} (last {args.since})")
    print()
    header = (f"  {group_by:<{name_w}}  "
              + "  ".join(f"{c:>9}" for c in cols)
              + "  flag")
    print(header)
    flagged: list[str] = []
    for s in services:
        row_vals = [counts[c].get(s, 0) for c in cols]
        # Flag on restart-flapping (above deploy floor), any OOM, any
        # unhandledRejection (config regression — see SKILL.md).
        # Uncaught isn't a flag input because it almost always rolls
        # into a restart, which we already count.
        flag = " ⚠" if (row_vals[0] > args.threshold
                       or row_vals[3] > 0
                       or row_vals[2] > 0) else ""
        if flag:
            flagged.append(s)
        print(f"  {s:<{name_w}}  "
              + "  ".join(f"{v:>9}" for v in row_vals)
              + f"  {flag}")

    if not flagged:
        return 0

    print()
    print("## last lines before most recent restart "
          "(flagged services)")
    restart_pat = SIGNALS[0][1]
    now_ns = time.time_ns()

    for s in flagged:
        # Find the most recent restart banner timestamp for this service.
        restarts = fetch_lines(lokictl, group_by, s, restart_pat,
                               args.since, "0s",
                               args.context_limit, args.addr)
        if not restarts:
            continue
        latest_ts = restarts[-1][0]

        # Fetch every line in the 60s preceding that restart. lokictl's
        # window is relative-to-now, so translate latest_ts into a
        # relative window.
        seconds_ago_latest = max(0, (now_ns - latest_ts) // 1_000_000_000)
        seconds_ago_ctx_start = seconds_ago_latest + 60
        ctx = fetch_lines(lokictl, group_by, s, ".",
                          f"{seconds_ago_ctx_start}s",
                          f"{seconds_ago_latest}s",
                          args.context_limit, args.addr)
        before = [(ts, ln) for ts, ln in ctx if ts < latest_ts]
        before = before[-args.samples:]
        latest_str = time.strftime("%H:%M:%S",
                                   time.localtime(latest_ts / 1e9))
        print(f"\n### {s} — last restart at {latest_str}")
        if not before:
            print("  (no preceding lines in 60s window)")
        for ts, line in before:
            ts_str = time.strftime("%H:%M:%S",
                                   time.localtime(ts / 1e9))
            print(f"  {ts_str}  {line[:240].replace(chr(10), ' ')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
