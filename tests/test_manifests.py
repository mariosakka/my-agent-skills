"""Marketplace and plugin manifest consistency (the same rules scripts/validate.sh enforces, in Python)."""
import json
import shutil
import subprocess

import pytest

from conftest import BASH, PLUGINS, REPO

MARKETPLACES = [REPO / ".claude-plugin" / "marketplace.json", REPO / ".agents" / "plugins" / "marketplace.json",
                REPO / ".muse-plugin" / "marketplace.json"]
MANIFESTS = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json"]
PLUGIN_DIRS = sorted(p for p in PLUGINS.iterdir() if p.is_dir())


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


@pytest.mark.parametrize("plugin", PLUGIN_DIRS, ids=lambda p: p.name)
def test_plugin_manifests_agree(plugin):
    loaded = [load(plugin / m) for m in MANIFESTS]
    assert {m["name"] for m in loaded} == {plugin.name}
    versions = {m["version"] for m in loaded}
    assert len(versions) == 1, f"versions differ across manifests: {versions}"
    assert all(m.get("description") for m in loaded)


@pytest.mark.parametrize("market", [m for m in MARKETPLACES if m.exists()], ids=lambda m: str(m.relative_to(REPO)))
def test_marketplace_lists_every_plugin_with_existing_source(market):
    data = load(market)
    listed = {}
    for entry in data["plugins"]:
        src = entry["source"] if isinstance(entry["source"], str) else entry["source"].get("path", "")
        assert src.startswith("./"), f"{entry['name']}: source must start with ./"
        assert ".." not in src.split("/"), f"{entry['name']}: source must not contain .."
        assert (REPO / src).is_dir(), f"{entry['name']}: {src} does not exist"
        listed[entry["name"]] = src
    assert set(listed) == {p.name for p in PLUGIN_DIRS}


def test_claude_marketplace_has_name_and_owner():
    data = load(MARKETPLACES[0])
    assert data["name"] and data["owner"]["name"]


def test_each_skill_belongs_to_exactly_one_plugin():
    names = [p.parent.name for p in PLUGINS.glob("*/skills/*/SKILL.md")]
    assert len(names) == len(set(names))


def test_release_please_versions_cover_and_match_every_plugin_manifest():
    config = load(REPO / "release-please-config.json")
    versions = load(REPO / ".release-please-manifest.json")
    expected = {f"plugins/{plugin.name}" for plugin in PLUGIN_DIRS}
    assert set(config["packages"]) == expected
    assert set(versions) == expected

    for plugin in PLUGIN_DIRS:
        package = f"plugins/{plugin.name}"
        release = config["packages"][package]
        version = versions[package]
        assert release["release-type"] == "simple"
        assert release["component"] == plugin.name
        assert (plugin / release["version-file"]).read_text(encoding="utf-8").strip() == version
        expected_paths = set(MANIFESTS)
        assert {item["path"] for item in release["extra-files"]} == expected_paths
        for manifest in MANIFESTS:
            assert (plugin / manifest).is_file()
            assert load(plugin / manifest)["version"] == version


def test_docs_sync_guard_requires_docs_for_implementation_and_test_changes():
    from scripts.check_docs_sync import check_paths

    status, _ = check_paths(["scripts/run_tests.sh"])
    assert status == 1
    status, _ = check_paths(["plugins/general/skills/example/tests/test_example.py"])
    assert status == 1
    for path in ("lib/anime_detail_test.dart", "src/search.test.ts", "src/search.spec.ts"):
        assert check_paths([path])[0] == 1
    status, _ = check_paths(["scripts/run_tests.sh", "README.md"])
    assert status == 0
    status, _ = check_paths(["plugins/general/skills/example/tests/test_example.py", "README.md"])
    assert status == 0


def test_docs_sync_guard_allows_docs_only_changes():
    from scripts.check_docs_sync import check_paths

    assert check_paths(["README.md"])[0] == 0


def test_docs_sync_guard_requires_a_reasoned_bypass():
    from scripts.check_docs_sync import check_paths

    assert check_paths(["scripts/run_tests.sh"], "Docs-Not-Required: internal refactor")[0] == 0
    assert check_paths(["tests/test_manifests.py"], "Docs-Not-Required: assertion-only correction")[0] == 0
    assert check_paths(["scripts/run_tests.sh"], "Docs-Not-Required:")[0] == 1


def test_validate_script_passes():
    if not (BASH and shutil.which("jq")):
        pytest.skip("bash and jq are needed to run scripts/validate.sh")
    r = subprocess.run([BASH, (REPO / "scripts" / "validate.sh").as_posix()], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "validate.sh: OK" in r.stdout
