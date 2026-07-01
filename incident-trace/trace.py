#!/usr/bin/env python3
"""
incident-trace helper — fetch every log line matching an identifier
across all services and emit a single chronological timeline.

Implementation: shells out to `lokictl grep --json` for the actual
Loki fetch. This script is the policy + rendering layer (which
identifier becomes which regex, how the timeline is laid out, when
to print a date prefix, how to truncate). The HTTP/escape/retry
plumbing is lokictl's job.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# Shared lokictl discovery lives in a sibling _lokictl/ package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lokictl.find import find_lokictl  # noqa: E402


def format_ts(ts_ns: int, with_date: bool = False) -> str:
    sec = ts_ns / 1e9
    lt = time.localtime(sec)
    ms = int((sec - int(sec)) * 1000)
    fmt = "%m-%d %H:%M:%S" if with_date else "%H:%M:%S"

    return time.strftime(fmt, lt) + f".{ms:03d}"


def prettify(line: str) -> str:
    """Unwrap Winston-style JSON-in-message logs."""
    idx = line.find("{")
    if idx < 0:
        return line
    prefix = line[:idx].rstrip()
    try:
        obj = json.loads(line[idx:])
    except json.JSONDecodeError:
        return line
    if isinstance(obj, dict) and isinstance(obj.get("message"), str):
        msg = obj["message"]
        level = obj.get("level", "")
        return (f"{prefix} {level}: {msg}".strip()
                if level else f"{prefix} {msg}".strip())

    return line


def main() -> int:
    p = argparse.ArgumentParser(prog="loki-trace")
    p.add_argument("identifier",
                   help="identifier to search for (UUID, AWB, order id, "
                        "email, ...). Comma-separate for OR.")
    p.add_argument("--since", default="24h",
                   help="window (default 24h)")
    p.add_argument("--limit", type=int, default=1000,
                   help="max lines per stream (default 1000)")
    p.add_argument("--service",
                   help="restrict to swarm_service substring")
    p.add_argument("--pretty", action="store_true",
                   help="unwrap Winston-style JSON-in-message")
    p.add_argument("--full", action="store_true",
                   help="print full lines (default truncates to 240 chars)")
    p.add_argument("--addr",
                   help="Loki URL (passed to lokictl; defaults to "
                        "lokictl's own default / LOKI_ADDR env var)")
    args = p.parse_args()

    lokictl = find_lokictl()

    ids = [i.strip() for i in args.identifier.split(",") if i.strip()]
    if not ids:
        sys.stderr.write("error: empty identifier\n")

        return 2

    # Build a single regex of literal alternatives. re.escape over-escapes
    # vs. RE2 (escapes a few chars RE2 doesn't require) but RE2 accepts
    # the extra backslashes inside a backtick literal, so this is safe.
    pattern = "|".join(re.escape(i) for i in ids)

    cmd = [
        lokictl, "grep",
        "--json",
        "--since", args.since,
        "--limit", str(args.limit),
        "-B", "0", "-A", "0",
    ]
    if args.service:
        cmd.extend(["--service", args.service])
    if args.addr:
        cmd.extend(["--addr", args.addr])
    cmd.append(pattern)

    # Stream stderr through to the user (lokictl prints query/range
    # preamble + "no matches" / unreachability errors there).
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, text=True,
                              timeout=120)
    except subprocess.TimeoutExpired:
        sys.stderr.write("error: lokictl timed out after 120s\n")

        return 124

    events: list[tuple[int, str, str]] = []
    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            sys.stderr.write(f"warn: skipping malformed line: {raw[:120]}\n")
            continue
        labels = obj.get("labels", {})
        sn = (labels.get("swarm_service")
              or labels.get("service_name", "?"))
        try:
            ts_ns = int(obj["ts_ns"])
            line = str(obj["line"])
        except (KeyError, TypeError, ValueError):
            sys.stderr.write(
                "warn: skipping JSON with missing/invalid ts_ns or line\n")
            continue
        events.append((ts_ns, sn, line))

    if not events:
        # lokictl already printed "no matches" or an error to stderr.
        return proc.returncode if proc.returncode != 0 else 1

    events.sort(key=lambda x: x[0])
    services = sorted({e[1] for e in events})
    sys.stderr.write(f"{len(events)} event(s) across "
                     f"{len(services)} service(s): "
                     f"{', '.join(services)}\n\n")

    # Show MM-DD prefix when the timeline crosses a day boundary,
    # otherwise the eye reads "09:20 < 16:35" and assumes time travel.
    days = {time.localtime(ts / 1e9).tm_yday for ts, _, _ in events}
    with_date = len(days) > 1

    width = max(len(s) for _, s, _ in events)
    for ts, svc, line in events:
        line = line.rstrip("\n")
        if args.pretty:
            line = prettify(line)
        if not args.full and len(line) > 240:
            line = line[:237] + "..."
        ts_str = format_ts(ts, with_date=with_date)
        if args.pretty and "\n" in line:
            head, *rest = line.split("\n")
            print(f"{ts_str}  [{svc:<{width}}]  {head}")
            indent = " " * (len(ts_str) + 4 + width + 2)
            for r in rest:
                print(f"{indent}{r}")
        else:
            line = line.replace("\n", " ")
            print(f"{ts_str}  [{svc:<{width}}]  {line}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
