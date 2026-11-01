#!/usr/bin/env python3
"""Check AGENTS.md and CLAUDE.md line limits and inline local Markdown links."""

import argparse
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


INSTRUCTION_NAMES = {"agents.md", "claude.md"}
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "build", "dist", "__pycache__"}
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"`[^`]*`")


def instruction_files(root):
    found = []
    for current, directories, names in os.walk(root):
        directories[:] = [name for name in directories if name not in IGNORED_DIRS]
        found.extend(
            Path(current) / name for name in names
            if name.lower() in INSTRUCTION_NAMES
        )
    return sorted(found)


def local_link_targets(document):
    in_fence = False
    for line_number, line in enumerate(document.splitlines(), 1):
        fence = FENCE.match(line)
        if fence:
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = INLINE_CODE.sub("", line)
        for match in LINK.finditer(line):
            raw_target = match.group(1).strip()
            if raw_target.startswith("<") and ">" in raw_target:
                raw_target = raw_target[1:raw_target.index(">")]
            else:
                raw_target = raw_target.split(maxsplit=1)[0]
            parsed = urlsplit(raw_target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            yield line_number, unquote(parsed.path)


def check_repo(root, max_lines):
    failures = []
    files = instruction_files(root)
    for instruction in files:
        relative = instruction.relative_to(root).as_posix()
        lines = instruction.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > max_lines:
            failures.append(f"{relative}: {len(lines)} lines exceeds {max_lines}")
        for line_number, target in local_link_targets("\n".join(lines)):
            candidate = (root / target.lstrip("/")) if target.startswith("/") else (instruction.parent / target)
            resolved = candidate.resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                failures.append(f"{relative}:{line_number}: link escapes repository: {target}")
                continue
            if not resolved.exists():
                failures.append(f"{relative}:{line_number}: broken local link: {target}")

    return files, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="repository root (default: current directory)")
    parser.add_argument("--max-lines", type=int, default=300)
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    if args.max_lines < 1:
        parser.error("--max-lines must be positive")

    files, failures = check_repo(root, args.max_lines)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    if files:
        print(f"PASS agent instructions: {len(files)} file(s), inline local links valid, max {args.max_lines} lines")
    else:
        print("INFO no AGENTS.md or CLAUDE.md files found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
