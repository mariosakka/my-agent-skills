import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="PowerShell is unavailable")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_repo(root):
    (root / "plugins/sample/skills/demo").mkdir(parents=True)
    (root / "plugins/sample/skills/demo/SKILL.md").write_text(
        "---\nname: demo\ndescription: >-\n  A demo skill.\n---\n", encoding="utf-8"
    )
    for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json"):
        write_json(root / "plugins/sample" / manifest, {"name": "sample", "version": "1.0.0"})
    entry = {"name": "sample", "source": "./plugins/sample"}
    write_json(root / ".claude-plugin/marketplace.json", {"name": "test", "plugins": [entry]})
    write_json(root / ".agents/plugins/marketplace.json", {"plugins": [entry]})


def run_validator(root):
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), "-RepoRoot", str(root)],
        capture_output=True, text=True, timeout=30,
    )


def test_powershell_validator_accepts_consistent_repository():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_repo(root)
        result = run_validator(root)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "validate.ps1: OK (1 skills, 1 plugins)" in result.stdout


def test_powershell_validator_reports_manifest_drift():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_repo(root)
        write_json(root / "plugins/sample/.muse-plugin/plugin.json", {"name": "sample", "version": "2.0.0"})
        result = run_validator(root)

    assert result.returncode == 1
    assert "version '2.0.0' != '1.0.0'" in result.stdout
