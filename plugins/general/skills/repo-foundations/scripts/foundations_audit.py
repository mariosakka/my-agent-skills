#!/usr/bin/env python3
"""Check observable repository-foundation signals; heuristic, not a quality proof."""

import argparse
import os
from pathlib import Path
import re
import sys


CI_FILES = (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", ".circleci/config.yml")
TEST_FILE = re.compile(r"(?:^test_.*|.*_test\.[^.]+|.*\.test\.[^.]+)$", re.IGNORECASE)
TEST_COMMAND = re.compile(
    r"\b(pytest|unittest|vitest|jest|cargo\s+test|go\s+test|gradle\s+test|"
    r"flutter\s+test|npm\s+test|pnpm\s+test|yarn\s+test|dotnet\s+test|"
    r"mvn\s+test|make\s+test|scripts/run_tests\.sh)\b",
    re.IGNORECASE,
)
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "build", "dist", "__pycache__"}


def audit_repo(repo):
    repo = Path(repo).resolve()
    files = []
    for root, directories, names in os.walk(repo):
        directories[:] = [name for name in directories if name not in IGNORED_DIRS]
        files.extend(Path(root) / name for name in names)
    relative = {path.relative_to(repo).as_posix(): path for path in files}
    workflows = [path for name, path in relative.items() if name.startswith(".github/workflows/")]
    ci_files = workflows + [relative[name] for name in CI_FILES if name in relative]
    tests = [name for name in relative if any(part.lower() in {"test", "tests"} for part in Path(name).parts)
             or TEST_FILE.match(Path(name).name)]
    readme = next((path for name, path in relative.items() if Path(name).name.lower() == "readme.md"), None)
    dev_docs = any(
        name.lower() in {"contributing.md", "docs/development.md", "docs/dev.md"}
        or name.lower().startswith("docs/dev/")
        for name in relative
    )
    if readme:
        readme_text = readme.read_text(encoding="utf-8", errors="ignore").lower()
        dev_docs |= "test" in readme_text and any(term in readme_text for term in ("development", "ci", "contribut"))
    ci_mentions_tests = any(TEST_COMMAND.search(path.read_text(encoding="utf-8", errors="ignore")) for path in ci_files)
    hooks = any(name.startswith((".githooks/", ".husky/")) for name in relative)
    all_ci_and_hooks = [path for path in ci_files]
    all_ci_and_hooks.extend(path for name, path in relative.items()
                            if name.startswith((".githooks/", ".husky/")))
    has_docs_guard = any(
        re.search(r"docs?[_ -]?sync|check_docs_sync", path.read_text(encoding="utf-8", errors="ignore"), re.IGNORECASE)
        for path in all_ci_and_hooks
    )

    checks = [
        ("README", any(Path(name).name.lower() == "readme.md" for name in relative), True),
        ("ignore rules", ".gitignore" in relative, True),
        ("CI workflow", bool(ci_files), True),
        ("test files", bool(tests), True),
        ("CI runs tests (heuristic)", bool(ci_files) and ci_mentions_tests, True),
        ("developer/test guidance", dev_docs, True),
        ("local hook implementation present", hooks, False),
        ("docs/test synchronization guard", has_docs_guard, False),
        ("release automation", any("release" in name.lower() for name in relative
                                    if name.startswith((".github/workflows/", ".gitlab/"))), False),
        ("known-issues tracking", any("known-issues" in name.lower() or "known_issues" in name.lower()
                                      for name in relative), False),
    ]
    return [(name, "PASS" if passed else ("WARN" if required else "INFO"), required)
            for name, passed, required in checks]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="repository directory to inspect")
    args = parser.parse_args()
    repo = Path(args.repo)
    if not repo.is_dir():
        parser.error(f"not a directory: {repo}")
    checks = audit_repo(repo)
    for name, result, _required in checks:
        print(f"{result:4} {name}")
    missing_required = [name for name, result, required in checks if required and result != "PASS"]
    print("Heuristic audit only; review architecture, security, and project-specific risks manually.")
    return 1 if missing_required else 0


if __name__ == "__main__":
    sys.exit(main())
