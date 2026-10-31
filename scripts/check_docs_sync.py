#!/usr/bin/env python3
"""Require source/test co-changes and docs alongside implementation or test changes."""

import argparse
import os
import subprocess
import sys
from pathlib import PurePosixPath


DOC_SUFFIXES = {".md", ".rst", ".adoc"}
IMPLEMENTATION_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".css", ".dart", ".ex", ".exs", ".go",
    ".gradle", ".h", ".hpp", ".html", ".ini", ".java", ".js", ".jsx",
    ".json", ".kt", ".lua", ".m", ".mm", ".php", ".pl", ".ps1", ".py",
    ".r", ".rb", ".rs", ".sass", ".scala", ".scss", ".sh", ".sql", ".svelte",
    ".swift", ".toml", ".ts", ".tsx", ".vue", ".xml", ".yaml", ".yml",
}
SOURCE_SUFFIXES = IMPLEMENTATION_SUFFIXES - {
    ".gradle", ".ini", ".json", ".toml", ".xml", ".yaml", ".yml",
}
TEST_DIRS = {"test", "tests"}
NO_DOCS_MARKER = "Docs-Not-Required:"
NO_TESTS_MARKER = "Tests-Not-Required:"


def is_test_path(path):
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name.lower()
    return any(part.lower() in TEST_DIRS for part in parts) or name.startswith("test_") or any(
        marker in name for marker in ("_test.", ".test.", ".spec.")
    )


def is_documentation_required_path(path):
    parsed = PurePosixPath(path)
    if parsed.suffix.lower() in DOC_SUFFIXES:
        return False
    if path.startswith(("scripts/", ".githooks/", ".github/workflows/")):
        return True
    return is_test_path(path) or parsed.suffix.lower() in IMPLEMENTATION_SUFFIXES


def is_source_path(path):
    parsed = PurePosixPath(path)
    if is_test_path(path) or parsed.suffix.lower() in DOC_SUFFIXES:
        return False
    if path.startswith(("scripts/", ".githooks/", ".github/workflows/")):
        return True
    return parsed.suffix.lower() in SOURCE_SUFFIXES


def is_documentation_path(path):
    return PurePosixPath(path).suffix.lower() in DOC_SUFFIXES


def bypass_reason(value):
    for line in value.splitlines():
        key, separator, reason = line.partition(NO_DOCS_MARKER)
        if separator and not key.strip() and reason.strip():
            return reason.strip()
    return None


def marker_reason(value, marker):
    for line in value.splitlines():
        key, separator, reason = line.partition(marker)
        if separator and not key.strip() and reason.strip():
            return reason.strip()
    return None


def check_paths(paths, bypass_value=""):
    required = [path for path in paths if is_documentation_required_path(path)]
    documentation = [path for path in paths if is_documentation_path(path)]
    if not required or documentation:
        return 0, "Docs/change check passed."

    reason = bypass_reason(bypass_value)
    if reason:
        return 0, f"Docs/change check bypassed: {reason}"

    changed = "\n  ".join(required)
    return 1, (
        "Implementation, configuration, or test changes require a documentation update. "
        "Update the relevant Markdown docs, or add `Docs-Not-Required: <reason>` "
        "to the PR description (CI) or set DOC_SYNC_BYPASS_REASON before pushing.\n"
        f"Documentation-required paths:\n  {changed}"
    )


def check_test_sync(paths, deleted_paths=(), bypass_value=""):
    sources = [path for path in paths if is_source_path(path)]
    tests = [path for path in paths if is_test_path(path)]
    deleted = set(deleted_paths)
    changed_tests = [path for path in tests if path not in deleted]
    deleted_tests = [path for path in tests if path in deleted]
    changed_sources = [path for path in sources if path not in deleted]
    deleted_sources = [path for path in sources if path in deleted]

    reason = marker_reason(bypass_value, NO_TESTS_MARKER)
    if reason:
        return 0, f"Source/test check bypassed: {reason}"
    if changed_sources and not changed_tests:
        problem = "Source additions or edits require related test additions or updates."
    elif deleted_sources and not tests:
        problem = "Removing source behavior requires removing or updating its tests."
    elif deleted_tests and not sources and not changed_tests:
        problem = "Test deletions require a related source change; do not remove coverage alone."
    else:
        return 0, "Source/test check passed."

    changed = "\n  ".join(sources + tests)
    return 1, (
        f"{problem} Add `Tests-Not-Required: <reason>` to the PR description "
        "or set TEST_SYNC_BYPASS_REASON before pushing for a justified exception.\n"
        f"Source/test paths:\n  {changed}"
    )


def git(*args, check=True):
    result = subprocess.run(["git", *args], check=False, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result


def changed_paths(base, head):
    result = git("diff", "--name-only", "-z", base, head)
    return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def deleted_paths(base, head):
    result = git("diff", "--diff-filter=D", "--name-only", "-z", base, head)
    return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def default_remote_ref(remote):
    symbolic = git("symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD", check=False)
    if symbolic.returncode == 0:
        return symbolic.stdout.decode().strip().removeprefix("refs/remotes/")
    for branch in ("master", "main"):
        ref = f"{remote}/{branch}"
        if git("rev-parse", "--verify", ref, check=False).returncode == 0:
            return ref
    raise RuntimeError(f"Cannot find {remote}'s default branch; fetch it before pushing a new branch.")


def pre_push_ranges(remote):
    zero = "0" * 40
    ranges = []
    for line in sys.stdin:
        fields = line.split()
        if len(fields) != 4:
            raise RuntimeError(f"Unexpected pre-push input: {line.rstrip()}")
        _local_ref, local_sha, _remote_ref, remote_sha = fields
        if local_sha == zero:
            continue
        if remote_sha == zero:
            base_ref = default_remote_ref(remote)
            base = git("merge-base", base_ref, local_sha).stdout.decode().strip()
        else:
            if git("cat-file", "-e", f"{remote_sha}^{{commit}}", check=False).returncode:
                raise RuntimeError(f"Remote commit {remote_sha} is unavailable locally; fetch before pushing.")
            base = remote_sha
        ranges.append((base, local_sha))
    return ranges


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?")
    parser.add_argument("head", nargs="?")
    parser.add_argument("--pre-push", action="store_true")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()
    try:
        if args.pre_push:
            ranges = pre_push_ranges(args.remote)
        elif args.base and args.head:
            ranges = [(args.base, args.head)]
        else:
            parser.error("provide BASE HEAD or use --pre-push")
        if not ranges:
            print("Docs/change check passed (no branch updates).")
            return 0
        failures = []
        for base, head in ranges:
            paths = changed_paths(base, head)
            deleted = deleted_paths(base, head)
            for status, message in (
                check_paths(paths, os.environ.get("DOC_SYNC_BYPASS_REASON", "")),
                check_test_sync(paths, deleted, os.environ.get("TEST_SYNC_BYPASS_REASON", "")),
            ):
                print(message)
                if status:
                    failures.append(status)
        return 1 if failures else 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Docs/change check failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
