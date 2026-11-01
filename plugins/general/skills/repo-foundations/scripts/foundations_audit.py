#!/usr/bin/env python3
"""Check observable repository-foundation signals; heuristic, not a quality proof."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


CI_FILES = (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", ".circleci/config.yml")
TEST_FILE = re.compile(r"(?:^test_.*|.*_test\.[^.]+|.*\.test\.[^.]+)$", re.IGNORECASE)
TEST_COMMAND = re.compile(
    r"\b(pytest|unittest|vitest|jest|cargo\s+test|go\s+test|gradle\s+test|"
    r"flutter\s+test|npm\s+test|pnpm\s+test|yarn\s+test|dotnet\s+test|"
    r"mvn\s+test|make\s+test|scripts/run_tests\.sh)\b",
    re.IGNORECASE,
)
TEST_LAYERS = {
    "drift/contract": re.compile(r"\b(drift|contract|schema)\b", re.IGNORECASE),
    "unit": re.compile(r"\bunit\b", re.IGNORECASE),
    "integration": re.compile(r"\bintegration\b", re.IGNORECASE),
    "UI/component/accessibility": re.compile(r"\b(ui|component|accessibility|widget)\b", re.IGNORECASE),
    "end-to-end/smoke": re.compile(r"\b(e2e|smoke|acceptance)\b|end.to.end", re.IGNORECASE),
    "performance/load": re.compile(r"\b(performance|load|stress|benchmark)\b", re.IGNORECASE),
    "security/data integrity": re.compile(r"\b(security|privacy|backup|restore|migration)\b|data integrity", re.IGNORECASE),
    "domain-specific": re.compile(r"domain[- ]specific|other risk", re.IGNORECASE),
}
TEST_PLAN_HEADING = re.compile(r"^#{1,6}\s+.*\b(test|testing)\b.*\b(strategy|layers|coverage|matrix|plan)\b", re.IGNORECASE)
TEST_DECISION = re.compile(r"\bcovered\b|\bN/A\b|not applicable", re.IGNORECASE)
GUARD_SCRIPT = re.compile(r"(?:^|/)(?:scripts|tools)/check_[\w-]*(?:sync|updated|lifecycle)[\w-]*\.(?:py|sh)$", re.IGNORECASE)
SECRET_SCANNER = re.compile(r"gitleaks|trufflehog|detect-secrets|git-secrets|secretlint", re.IGNORECASE)
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "build", "dist", "__pycache__"}


def test_strategy_status(repo, relative):
    sections = []
    doc_names = [name for name in relative if name.lower() == "readme.md"
                 or (name.lower().endswith(".md") and any(term in name.lower()
                     for term in ("test", "quality", "development", "contribut")))]
    for name in doc_names:
        lines = relative[name].read_text(encoding="utf-8", errors="ignore").splitlines()
        active_level = None
        for line in lines:
            heading = re.match(r"^(#{1,6})\s+", line)
            if heading:
                level = len(heading.group(1))
                if active_level is not None and level <= active_level:
                    active_level = None
                if TEST_PLAN_HEADING.search(line):
                    active_level = level
                    continue
            if active_level is not None:
                sections.append(line)

    statuses = {}
    for label, pattern in TEST_LAYERS.items():
        status = "WARN"
        for line in sections:
            if not pattern.search(line) or not TEST_DECISION.search(line):
                continue
            if re.search(r"\bN/A\b|not applicable", line, re.IGNORECASE):
                if re.search(r"(?:N/A|not applicable)\s*[:\-]\s*\S.+", line, re.IGNORECASE):
                    status = "PASS"
                    break
            elif re.search(r"\bcovered\b", line, re.IGNORECASE):
                for reference in re.findall(r"`([^`]+)`", line):
                    candidate = Path(reference.rstrip("/"))
                    if (repo / candidate).exists():
                        status = "PASS"
                        break
                if status == "PASS":
                    break
        statuses[label] = status
    return statuses


def non_executable_scripts(repo):
    """Tracked files that start with a shebang but are not mode 100755."""
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "-s"], capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    bad = []
    for line in out.splitlines():
        meta, _, name = line.partition("	")
        if meta.split()[0] != "100644":
            continue
        try:
            with open(Path(repo) / name, "rb") as handle:
                if handle.read(2) == b"#!":
                    bad.append(name)
        except OSError:
            continue
    return bad


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
    ci_secret_scan = any(SECRET_SCANNER.search(path.read_text(encoding="utf-8", errors="ignore"))
                         for path in ci_files)
    hooks = any(name.startswith((".githooks/", ".husky/")) for name in relative)
    pre_push_hooks = [path for name, path in relative.items()
                      if name in {".githooks/pre-push", ".husky/pre-push"}]
    hook_secret_scan = any(SECRET_SCANNER.search(path.read_text(encoding="utf-8", errors="ignore"))
                           for path in pre_push_hooks)
    all_ci_and_hooks = [path for path in ci_files]
    all_ci_and_hooks.extend(path for name, path in relative.items()
                            if name.startswith((".githooks/", ".husky/")))
    guard_files = [path for name, path in relative.items() if GUARD_SCRIPT.search(name)]
    texts = [path.read_text(encoding="utf-8", errors="ignore") for path in all_ci_and_hooks]
    has_docs_guard = any(re.search(r"docs?[_ -]?sync|check_docs_sync", text, re.IGNORECASE)
                         or any(guard.name in text for guard in guard_files) for text in texts)
    sync_wired = any(
        "test" in guard.read_text(encoding="utf-8", errors="ignore").lower()
        and any(guard.name in text for text in texts)
        for guard in guard_files
    )

    checks = [
        ("README", any(Path(name).name.lower() == "readme.md" for name in relative), True),
        ("ignore rules", ".gitignore" in relative, True),
        ("CI workflow", bool(ci_files), True),
        ("test files", bool(tests), True),
        ("CI runs tests (heuristic)", bool(ci_files) and ci_mentions_tests, True),
        ("secret scanning in CI", ci_secret_scan, True),
        ("secret scanning in pre-push hook", hook_secret_scan, True),
        ("developer/test guidance", dev_docs, True),
        ("source/test change guard", bool(sync_wired), True),
        ("local hook implementation present", hooks, False),
        ("docs/test synchronization guard", has_docs_guard, False),
        ("release automation", any("release" in name.lower() for name in relative
                                    if name.startswith((".github/workflows/", ".gitlab/"))), False),
        ("tracked scripts are executable", not non_executable_scripts(repo), False),
        ("known-issues tracking", any("known-issues" in name.lower() or "known_issues" in name.lower()
                                      for name in relative), False),
    ]
    checks.extend((f"test strategy: {layer}", status == "PASS", True)
                  for layer, status in test_strategy_status(repo, relative).items())
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
