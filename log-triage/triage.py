#!/usr/bin/env python3
"""
log-triage helper — rank error-level log lines by service and message
signature over a configurable window.

Implementation: shells out to `lokictl count` for the per-service
aggregation (instant query, fast) and `lokictl grep` per top service
for sample lines that get clustered into signatures. This script owns
the signature/clustering policy and the rendering; lokictl owns the
Loki calls.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Shared lokictl discovery lives in a sibling _lokictl/ package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lokictl.find import find_lokictl  # noqa: E402


def signature(line: str) -> str:
    """Reduce a log line to a stable shape for clustering.

    Pull out the JSON message field (or fall back to the first 120 chars
    of the line), then collapse digit runs and quoted IDs to `*`.
    """
    m = re.search(r'"message":"([^"]{0,200})', line)
    raw = m.group(1) if m else line[:120]
    raw = raw[:120]
    raw = re.sub(r"\\n.*$", "", raw)
    raw = re.sub(r"\d{3,}", "*", raw)
    raw = re.sub(r"'[^']{6,}'", "'*'", raw)
    raw = re.sub(r'"[^"]{16,}"', '"*"', raw)

    return raw.strip()


def run_lokictl(cmd: list[str]) -> str:
    """Run a lokictl subcommand and return stdout.

    Returns the empty string on timeout or non-zero exit; in both cases
    a warning is written to stderr so a silent lokictl outage doesn't
    look like a clean "no errors" report.
    """
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              timeout=120)
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"warn: lokictl timed out: {' '.join(cmd)}\n")

        return ""
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        sys.stderr.write(
            f"warn: lokictl exited {proc.returncode}: {' '.join(cmd)}"
            + (f"\n  {err}\n" if err else "\n"))

        return ""

    return proc.stdout


def fetch_service_counts(lokictl: str, since: str, service: str | None,
                         addr: str | None) -> list[tuple[str, int]]:
    """Run `lokictl count --by swarm_service --level error`."""
    cmd = [lokictl, "count", "--by", "swarm_service",
           "--level", "error", "--since", since, "--json"]
    if service:
        cmd.extend(["--service", service])
    if addr:
        cmd.extend(["--addr", addr])

    out: list[tuple[str, int]] = []
    for raw in run_lokictl(cmd).splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        try:
            out.append((str(obj["value"]), int(obj["count"])))
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: -x[1])

    return out


def fetch_service_samples(lokictl: str, sn: str, since: str,
                          max_fetch: int, addr: str | None
                          ) -> list[tuple[int, str]]:
    """Run `lokictl grep` for one service, returning (ts_ns, line) rows.

    Uses an exact-match selector (not --service substring) because the
    aggregation already gave us the canonical swarm_service name; we
    don't want substring drift across similarly-named services.
    """
    # json.dumps handles quote/backslash escaping the way LogQL expects.
    selector = "{swarm_service=" + json.dumps(sn) + "}"
    cmd = [lokictl, "grep", "--json",
           "--since", since,
           "--level", "error",
           "--limit", str(max_fetch),
           "-B", "0", "-A", "0"]
    if addr:
        cmd.extend(["--addr", addr])
    cmd.extend([".", selector])

    out: list[tuple[int, str]] = []
    for raw in run_lokictl(cmd).splitlines():
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

    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="log-triage")
    p.add_argument("--since", default="24h",
                   help="window (default 24h)")
    p.add_argument("--top", type=int, default=8,
                   help="top N services to detail (default 8)")
    p.add_argument("--samples", type=int, default=3,
                   help="sample lines per signature (default 3)")
    p.add_argument("--service",
                   help="restrict to swarm_service substring")
    p.add_argument("--addr",
                   help="Loki URL (passed to lokictl)")
    p.add_argument("--max-fetch", type=int, default=2000,
                   help="max error lines to fetch per service "
                        "(default 2000)")
    args = p.parse_args()

    lokictl = find_lokictl()

    counts = fetch_service_counts(lokictl, args.since, args.service,
                                  args.addr)
    if not counts:
        print(f"no error-level lines in last {args.since}")

        return 0

    print(f"## errors per swarm_service (last {args.since})")
    print()
    width = max(len(sn) for sn, _ in counts)
    for sn, c in counts:
        print(f"  {c:6d}  {sn:<{width}}")
    print()

    print(f"## top message signatures (top {args.top} services)")
    for sn, total in counts[:args.top]:
        rows = fetch_service_samples(lokictl, sn, args.since,
                                     args.max_fetch, args.addr)
        per_sig: dict[str, list[tuple[int, str]]] = {}
        for ts, line in rows:
            sig = signature(line)
            per_sig.setdefault(sig, []).append((ts, line))

        ranked = sorted(per_sig.items(), key=lambda kv: -len(kv[1]))
        print()
        print(f"### {sn} ({total} errors, {len(ranked)} signatures)")
        for sig, items in ranked[:5]:
            print(f"  [{len(items):4d}]  {sig}")
            for _, line in items[:args.samples]:
                snippet = line[:240].replace("\n", " ")
                print(f"          {snippet}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
