#!/usr/bin/env python3
"""
courier-health helper — classify courier-integration errors by courier
and error class over a window.

Implementation: shells out to `lokictl grep --json` once per courier
with `--level error,warn` so the level filter is server-side (the
per-courier limit applies to already-filtered lines, not info/debug
noise that happens to mention the courier). This script owns the
courier taxonomy and the error-class classification; lokictl owns
the fetch.
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


COURIERS: list[tuple[str, str]] = [
    # (display_name, RE2 pattern matching the courier in a log line)
    ("FanCourier",  r"FanCourier|fan_courier|courier_fan_"),
    ("DragonStar",  r"DragonStar|dragonstar"),
    ("GLS",         r"GLS ERROR|\bGLS\b"),
    ("UPS",         r"UPS (GET|POST|PUT|DELETE)|\bUPS\b"),
    ("Sameday",     r"sameday|Sameday"),
    ("Cargus",      r"cargus|Cargus"),
]

CLASSES: list[tuple[str, re.Pattern]] = [
    ("network",   re.compile(
        r"socket hang up|ECONNRESET|ETIMEDOUT|ECONNREFUSED|"
        r"Request timed out|read ECONNRESET|connect ETIMEDOUT",
        re.IGNORECASE)),
    ("parse",     re.compile(
        r"Unexpected token|not valid JSON|<\?xml|"
        r"SyntaxError.*JSON",
        re.IGNORECASE)),
    ("http_4xx",  re.compile(
        r"status code 4\d\d|HTTP 4\d\d|\b4\d\d\b.*response",
        re.IGNORECASE)),
    ("http_5xx",  re.compile(
        r"status code 5\d\d|HTTP 5\d\d|\b5\d\d\b.*response|"
        r"Internal Server Error|Bad Gateway",
        re.IGNORECASE)),
]


def classify(line: str) -> str:
    for name, pat in CLASSES:
        if pat.search(line):
            return name

    return "app_error"


def fetch_courier_lines(lokictl: str, courier_pat: str, since: str,
                        limit: int, addr: str | None
                        ) -> list[tuple[int, str, str]]:
    """Return [(ts_ns, line, swarm_service)] for one courier pattern."""
    cmd = [
        lokictl, "grep",
        "--json",
        "--since", since,
        "--limit", str(limit),
        "-B", "0", "-A", "0",
        "--level", "error,warn",
    ]
    if addr:
        cmd.extend(["--addr", addr])
    cmd.append(courier_pat)

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True,
                              timeout=120)
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"warn: lokictl timed out for "
                         f"pattern {courier_pat!r}\n")

        return []
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        sys.stderr.write(
            f"warn: lokictl exited {proc.returncode} for pattern "
            f"{courier_pat!r}"
            + (f": {err}\n" if err else "\n"))

        return []

    out: list[tuple[int, str, str]] = []
    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        labels = obj.get("labels", {})
        sn = (labels.get("swarm_service")
              or labels.get("service_name", "?"))
        try:
            out.append((int(obj["ts_ns"]), str(obj["line"]), sn))
        except (KeyError, TypeError, ValueError):
            continue

    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="loki-courier-health")
    p.add_argument("--since", default="24h",
                   help="window (default 24h)")
    p.add_argument("--courier",
                   help="restrict to courier name substring "
                        "(matched against display name only)")
    p.add_argument("--samples", type=int, default=2,
                   help="sample lines per cell (default 2)")
    p.add_argument("--addr",
                   help="Loki URL (passed to lokictl)")
    p.add_argument("--limit", type=int, default=2000,
                   help="max lines fetched per courier (default 2000)")
    args = p.parse_args()

    lokictl = find_lokictl()

    couriers = COURIERS
    if args.courier:
        # Match against the display name only. Matching against the regex
        # pattern (the previous behavior) would let `--courier b` collide
        # with `\bGLS\b`, which is surprising.
        couriers = [c for c in COURIERS
                    if args.courier.lower() in c[0].lower()]
        if not couriers:
            sys.stderr.write(
                f"unknown courier: {args.courier!r}. "
                f"Known: {', '.join(c[0] for c in COURIERS)}\n")

            return 2

    classes = [n for n, _ in CLASSES] + ["app_error"]
    matrix: dict[str, dict[str, list]] = {
        c[0]: {cls: [] for cls in classes} for c in couriers
    }

    for cname, cpat in couriers:
        rows = fetch_courier_lines(lokictl, cpat, args.since,
                                   args.limit, args.addr)
        for ts, line, sn in rows:
            matrix[cname][classify(line)].append((ts, line, sn))

    # Print matrix
    name_w = max(len(c) for c in matrix) if matrix else 10
    cls_w = max(8, max(len(c) for c in classes))
    print(f"## courier × error_class (last {args.since})")
    print()
    header = (f"  {'courier':<{name_w}}  "
              + "  ".join(f"{c:>{cls_w}}" for c in classes)
              + f"  {'total':>6}")
    print(header)
    rows_with_data: list[tuple[str, dict, int]] = []
    for cname in matrix:
        cells = matrix[cname]
        total = sum(len(v) for v in cells.values())
        if total == 0:
            print(f"  {cname:<{name_w}}  "
                  + "  ".join(f"{0:>{cls_w}}" for _ in classes)
                  + f"  {0:>6}")
            continue
        rows_with_data.append((cname, cells, total))
        print(f"  {cname:<{name_w}}  "
              + "  ".join(f"{len(cells[c]):>{cls_w}}" for c in classes)
              + f"  {total:>6}")

    if rows_with_data:
        print()
        print("## samples (loudest cells first)")
        loudest: list[tuple[int, str, str, list]] = []
        for cname, cells, _ in rows_with_data:
            for cls in classes:
                items = cells[cls]
                if items:
                    loudest.append((len(items), cname, cls, items))
        loudest.sort(key=lambda x: -x[0])
        for n, cname, cls, items in loudest[:8]:
            print(f"\n### {cname} / {cls} ({n})")
            for _, line, sn in items[:args.samples]:
                snippet = line[:240].replace("\n", " ")
                print(f"  [{sn}] {snippet}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
