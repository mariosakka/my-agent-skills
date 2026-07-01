"""Shared lokictl discovery for the colete-online log skills.

Each skill that shells out to `lokictl` imports `find_lokictl` from
here. The first successful resolution is cached in a sibling `.path`
file so subsequent invocations — across all skills — skip the search.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent / ".path"


def find_lokictl() -> str:
    """Resolution order:

    1. Cached absolute path from a previous successful resolution.
    2. `lokictl` on PATH (the conventional Unix install).
    3. Walk up from CWD looking for a colete-online checkout
       (`<root>/scripts/lokictl`).

    Caches the first hit so future invocations work from any directory.
    Stale cache entries fall through to fresh discovery.
    """
    if CACHE_PATH.exists():
        try:
            p = CACHE_PATH.read_text().strip()
        except (OSError, UnicodeDecodeError):
            p = ""
        if p and Path(p).is_file() and os.access(p, os.X_OK):
            return p

    found = shutil.which("lokictl")
    if found:
        try:
            CACHE_PATH.write_text(found)
        except OSError:
            pass

        return found

    cwd = Path.cwd().resolve()
    for d in [cwd, *cwd.parents]:
        candidate = d / "scripts" / "lokictl"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            try:
                CACHE_PATH.write_text(str(candidate))
            except OSError:
                pass

            return str(candidate)

    sys.stderr.write(
        "error: lokictl not found. Either symlink it into PATH:\n"
        "  ln -sf <repo>/scripts/lokictl ~/.local/bin/lokictl\n"
        "or run a lokictl-based skill once from inside a colete-online "
        "checkout (the path will be cached for future invocations).\n")
    sys.exit(127)
