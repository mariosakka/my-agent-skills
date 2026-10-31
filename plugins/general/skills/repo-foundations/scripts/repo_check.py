#!/usr/bin/env python3
"""Report a read-only Git inventory and likely sensitive staged filenames."""

import argparse
import os
from pathlib import PurePath
import subprocess
import sys


def git(repo, *args):
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES"):
        env.pop(key, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env,
    ).stdout


def sensitive(path):
    # shortcut: filename heuristics miss secrets in other files, use a secret scanner for broader checks
    name = PurePath(path.replace("\\", "/")).name.lower()
    return (
        name == ".env" or name.startswith(".env.")
        or name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"))
        or any(word in name for word in ("private_key", "private-key", "personal_export", "personal-export"))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="path to the Git repository")
    args = parser.parse_args()
    try:
        status = git(args.repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        staged = git(args.repo, "diff", "--cached", "--name-only", "-z", "--no-renames")
        worktrees = git(args.repo, "worktree", "list", "--porcelain", "-z")
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = os.fsdecode(exc.stderr).strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"Git error: {detail}", file=sys.stderr)
        return 2

    print("Status (porcelain):")
    records = iter(status.split(b"\0"))
    for record in records:
        if not record:
            continue
        print(f"  {os.fsdecode(record[:2])} {os.fsdecode(record[3:])!r}")
        if b"R" in record[:2] or b"C" in record[:2]:
            print(f"    from {os.fsdecode(next(records))!r}")
    print("Worktrees:")
    for field in worktrees.split(b"\0"):
        if field:
            key, _, value = field.partition(b" ")
            print(f"  {os.fsdecode(key)} {os.fsdecode(value)!r}")
    paths = [os.fsdecode(path) for path in staged.split(b"\0") if path]
    print("Staged paths:")
    for path in paths:
        print(f"  {path!r}")
    flagged = [path for path in paths if sensitive(path)]
    print("Likely sensitive staged paths:")
    for path in flagged:
        print(f"  {path!r}")
    if not flagged:
        print("  None identified.")
    print("Filename checks are incomplete; contents and history were not inspected.")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
