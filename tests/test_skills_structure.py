"""Structure checks that apply to every skill (frontmatter, referenced paths, script syntax)."""
import ast
import py_compile
import re
import subprocess
from pathlib import Path

import pytest

from conftest import BASH, skill_dirs  # noqa: F401  (root conftest, importable as a plain module)

SKILLS = skill_dirs()
IDS = [f"{d.parent.parent.name}/{d.name}" for d in SKILLS]


def frontmatter(skill_md):
    text = skill_md.read_text(encoding="utf-8").replace("\r\n", "\n").lstrip("﻿")
    assert text.startswith("---\n"), "SKILL.md must open with a --- frontmatter block"
    body = text[4:]
    assert "\n---" in body, "frontmatter is not closed"
    return body.split("\n---", 1)[0]


def field(fm, key):
    m = re.search(rf"^{key}:[ \t]*(.*(?:\n[ \t]+.*)*)", fm, re.M)
    return None if not m else re.sub(r"\s+", " ", m.group(1)).strip().strip("\"'")


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_frontmatter_name_matches_folder_and_description_present(skill):
    fm = frontmatter(skill / "SKILL.md")
    assert field(fm, "name") == skill.name
    desc = field(fm, "description")
    assert desc and desc not in (">", "|", ">-", "|-"), "description is empty"


REF_RE = re.compile(r"(?<![\w~./<>-])((?:scripts|references|config)/[\w./-]+)")


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_relative_paths_in_skill_md_exist(skill):
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    missing = []
    for ref in set(REF_RE.findall(text)):
        ref = ref.rstrip(".,:;)")
        if "*" in ref or not re.search(r"\.\w+$", ref):
            continue  # globs and directories
        if not (skill / ref).exists():
            missing.append(ref)
    assert not missing, f"SKILL.md mentions files that do not exist: {sorted(missing)}"


def scripts(skill):
    files = [p for p in skill.rglob("*") if p.is_file() and "tests" not in p.relative_to(skill).parts
             and "__pycache__" not in p.parts]
    return [p for p in files if p.suffix in (".sh", ".py") or p.parent == skill and not p.suffix and p.name != "LICENSE"
            and p.read_text(encoding="utf-8", errors="ignore").startswith("#!")]


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_scripts_have_valid_syntax_and_lf_endings(skill, tmp_path):
    for script in scripts(skill):
        raw = script.read_bytes()
        if script.suffix == ".sh":
            assert b"\r" not in raw, f"{script.name}: CRLF line endings"
            if BASH:
                r = subprocess.run([BASH, "-n", script.as_posix()], capture_output=True, text=True)
                assert r.returncode == 0, f"{script.name}: {r.stderr}"
        elif script.suffix == ".py":
            py_compile.compile(str(script), cfile=str(tmp_path / "x.pyc"), doraise=True)
        else:  # extension-less executable with a shebang
            if b"python" in raw.splitlines()[0]:
                ast.parse(raw.decode("utf-8"))
            elif BASH:
                r = subprocess.run([BASH, "-n", script.as_posix()], capture_output=True, text=True)
                assert r.returncode == 0, f"{script.name}: {r.stderr}"


def test_every_skill_found():
    assert len(SKILLS) >= 9


def test_lab_creation_skill_requires_lab_update_hook_with_bypass():
    skill = next(skill for skill in SKILLS if skill.name == "lab-creation")
    text = (skill / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "git hook" in text
    assert "lab index" in text
    assert "shared environment" in text
    assert "documented bypass" in text


def test_lab_creation_requires_indexed_reusable_tools_and_automation():
    skill = next(skill for skill in SKILLS if skill.name == "lab-creation")
    text = " ".join((skill / "SKILL.md").read_text(encoding="utf-8").lower().split())
    assert "small, reusable set of tools" in text
    assert "purpose, prerequisites, and exact invocation" in text
    assert "actively look for repeated manual updates" in text
    assert "do not create placeholder tools" in text


def test_repo_foundations_requires_indexed_reusable_tools_and_automation():
    skill = next(skill for skill in SKILLS if skill.name == "repo-foundations")
    text = " ".join((skill / "SKILL.md").read_text(encoding="utf-8").lower().split())
    quality = " ".join(
        (skill / "references" / "architecture-and-quality.md")
        .read_text(encoding="utf-8")
        .lower()
        .split()
    )
    assert "reusable developer-tooling set" in text
    assert "canonical developer entrypoint" in text
    assert "actively look for repeated" in text
    assert "do not create placeholder tools" in text
    assert "canonical index" in quality
    assert "development, test, ci, and release" in quality


def test_repo_foundations_covers_environment_automation_and_issue_intake():
    skill = next(skill for skill in SKILLS if skill.name == "repo-foundations")
    operations = " ".join(
        (skill / "references" / "operations-and-hygiene.md")
        .read_text(encoding="utf-8")
        .lower()
        .split()
    )
    pipelines = " ".join(
        (skill / "references" / "ci-and-release.md")
        .read_text(encoding="utf-8")
        .lower()
        .split()
    )
    assert "docker compose" in operations
    assert "scripts or task-runner commands" in operations
    assert "canonical developer-tool index" in operations
    assert "seed data" in operations
    assert "never seed production automatically" in operations
    assert "github app" in operations
    assert "idempotency key" in operations
    assert "deduplicate on the server" in operations
    assert "redaction" in operations
    assert "dependabot" in pipelines
    assert "auto-merge" in pipelines
    assert "build once and promote" in pipelines


def test_repo_foundations_requires_measured_network_and_cache_efficiency():
    skill = next(skill for skill in SKILLS if skill.name == "repo-foundations")
    quality = " ".join(
        (skill / "references" / "architecture-and-quality.md")
        .read_text(encoding="utf-8")
        .lower()
        .split()
    )
    assert "request counts, payload sizes" in quality
    assert "batch related lookups" in quality
    assert "deduplicate identical in-flight work" in quality
    assert "cache policy per data type" in quality
    assert "freshness/ttl, invalidation" in quality
    assert "request and performance budgets" in quality
    assert "maintained request/performance ledger" in quality
    assert "measured savings" in quality


def test_repo_foundations_requires_secret_scanning_in_ci_and_pre_push():
    skill = next(skill for skill in SKILLS if skill.name == "repo-foundations")
    body = " ".join((skill / "SKILL.md").read_text(encoding="utf-8").lower().split())
    pipelines = " ".join(
        (skill / "references" / "ci-and-release.md")
        .read_text(encoding="utf-8")
        .lower()
        .split()
    )
    assert "require gitleaks or an equivalent in ci and in the installed pre-push hook" in body
    assert "scheduled full-history scan" in pipelines
    assert "must fail with installation instructions" in pipelines


def test_current_repo_runs_pinned_gitleaks_in_ci_and_pre_push():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "validate.yml")
    scheduled_workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "secret-scan.yml")
    hook = (Path(__file__).resolve().parents[1] / ".githooks" / "pre-push")
    workflow_text = workflow.read_text(encoding="utf-8").lower()
    scheduled_text = scheduled_workflow.read_text(encoding="utf-8").lower()
    hook_text = hook.read_text(encoding="utf-8").lower()
    assert "pull_request:" in workflow_text
    assert re.search(r"gitleaks/gitleaks-action@[0-9a-f]{40}", workflow_text)
    assert "gitleaks_version: 8.30.1" in workflow_text
    assert "schedule:" in scheduled_text
    assert "gitleaks git" in hook_text
    assert "command -v gitleaks" in hook_text


def test_release_please_auto_merge_requires_successful_validation_of_exact_head():
    root = Path(__file__).resolve().parents[1]
    release = (root / ".github" / "workflows" / "release-please.yml").read_text(encoding="utf-8").lower()
    validate = (root / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8").lower()
    assert "actions: write" in release
    assert "gh workflow run validate.yml --ref \"$branch\"" in release
    assert "auto-merge-release-please:" in validate
    assert "needs: validate" in validate
    assert "github.event_name == 'workflow_dispatch'" in validate
    assert "refs/heads/release-please--branches--master" in validate
    assert "app/github-actions" in validate
    assert '"$pr_sha" != "$validated_sha"' in validate
    assert "--match-head-commit \"$validated_sha\"" in validate


def test_repo_foundations_requires_api_contract_generation_and_publication_rules():
    skill = next(skill for skill in SKILLS if skill.name == "repo-foundations")
    pipelines = " ".join(
        (skill / "references" / "ci-and-release.md")
        .read_text(encoding="utf-8")
        .lower()
        .split()
    )
    assert "one source of truth for the public api contract" in pipelines
    assert "fail on unexplained drift" in pipelines
    assert "breaking compatibility" in pipelines
    assert "generated clients" in pipelines
    assert "publish versioned, immutable schemas" in pipelines
    assert "publishing api documentation/contracts is distinct from" in pipelines
    assert "record the source commit, artifact version/checksum" in pipelines
