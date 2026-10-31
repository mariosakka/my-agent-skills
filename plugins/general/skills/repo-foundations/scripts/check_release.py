#!/usr/bin/env python3
"""Check a local release tag, expected commit, and working tree."""

import argparse
import os
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="path to the Git repository")
    parser.add_argument("tag", help="exact local tag name")
    parser.add_argument("commit", help="expected full commit object ID")
    args = parser.parse_args()
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", args.commit):
        parser.error("commit must be a full 40- or 64-character hexadecimal object ID")

    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES"):
        env.pop(key, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"

    def git(*arguments, check=True):
        return subprocess.run(["git", "-C", args.repo, *arguments], check=check,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    try:
        git("rev-parse", "--git-dir")
        ref = "refs/tags/" + args.tag
        if git("check-ref-format", ref, check=False).returncode:
            parser.error("invalid tag name")
        tag = git("show-ref", "--verify", "--quiet", ref, check=False)
        if tag.returncode not in (0, 1):
            raise subprocess.CalledProcessError(tag.returncode, tag.args, stderr=tag.stderr)
        if tag.returncode == 1:
            print(f"Missing tag: {args.tag}")
            return 1
        actual = git("rev-parse", "--verify", ref + "^{commit}").stdout.strip().decode("ascii")
        head = git("rev-parse", "--verify", "HEAD^{commit}").stdout.strip().decode("ascii")
        status = git("status", "--porcelain=v1", "-z", "--untracked-files=all",
                     "--ignore-submodules=none").stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = os.fsdecode(exc.stderr).strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        print(f"Git error: {detail}", file=sys.stderr)
        return 2

    if actual != args.commit.lower():
        print(f"Tag commit mismatch: expected {args.commit.lower()}, found {actual}")
    if head != actual:
        print(f"Checkout commit mismatch: HEAD is {head}, tag is {actual}")
    if status:
        print("Working tree is dirty.")
    if actual != args.commit.lower() or head != actual or status:
        return 1
    print(f"Tag {args.tag} resolves to {actual}; working tree is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
