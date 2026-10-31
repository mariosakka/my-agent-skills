from pathlib import Path
import importlib.util
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "foundations_audit.py"
SPEC = importlib.util.spec_from_file_location("foundations_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FoundationsAuditTests(unittest.TestCase):
    def test_reports_required_signals_and_optional_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "README.md").write_text("project", encoding="utf-8")
            (repo / ".gitignore").write_text(".venv/", encoding="utf-8")
            (repo / "CONTRIBUTING.md").write_text("Run tests with pytest", encoding="utf-8")
            (repo / "tests").mkdir()
            (repo / "tests" / "test_example.py").write_text("def test_ok(): pass", encoding="utf-8")
            (repo / ".github" / "workflows").mkdir(parents=True)
            (repo / ".github" / "workflows" / "ci.yml").write_text("run: pytest", encoding="utf-8")

            checks = {name: status for name, status, _ in AUDIT.audit_repo(repo)}

        self.assertEqual(checks["README"], "PASS")
        self.assertEqual(checks["CI runs tests (heuristic)"], "PASS")
        self.assertEqual(checks["local hook implementation present"], "INFO")

    def test_warns_when_required_foundation_signals_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            checks = {name: (status, required) for name, status, required in AUDIT.audit_repo(directory)}

        self.assertEqual(checks["CI workflow"], ("WARN", True))
        self.assertEqual(checks["test files"], ("WARN", True))


if __name__ == "__main__":
    unittest.main()
