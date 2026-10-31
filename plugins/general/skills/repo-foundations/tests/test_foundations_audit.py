from pathlib import Path
import importlib.util
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "foundations_audit.py"
SPEC = importlib.util.spec_from_file_location("foundations_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def add_test_strategy(repo):
    tests = repo / "tests"
    tests.mkdir(exist_ok=True)
    evidence = tests / "test_evidence.py"
    evidence.write_text("def test_evidence(): pass", encoding="utf-8")
    rows = [
        "| Drift/contract | Covered | `tests/test_evidence.py` |",
        "| Unit | Covered | `tests/test_evidence.py` |",
        "| Integration | Covered | `tests/test_evidence.py` |",
        "| UI/component/accessibility | N/A: no product interface. |",
        "| End-to-end/smoke | Covered | `tests/test_evidence.py` |",
        "| Performance/load | N/A: no runtime workload. |",
        "| Security/data integrity | Covered | `tests/test_evidence.py` |",
        "| Domain-specific | N/A: reassess for new domains. |",
    ]
    (repo / "README.md").write_text("## Test Strategy\n\n" + "\n".join(rows), encoding="utf-8")


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
            (repo / ".github" / "workflows" / "ci.yml").write_text(
                "run: pytest\npython scripts/check_docs_sync.py base head", encoding="utf-8"
            )
            (repo / "scripts").mkdir()
            (repo / "scripts" / "check_docs_sync.py").write_text("def check_test_sync(): pass", encoding="utf-8")
            add_test_strategy(repo)

            checks = {name: status for name, status, _ in AUDIT.audit_repo(repo)}

        self.assertEqual(checks["README"], "PASS")
        self.assertEqual(checks["CI runs tests (heuristic)"], "PASS")
        self.assertEqual(checks["source/test change guard"], "PASS")
        self.assertEqual(checks["test strategy: drift/contract"], "PASS")
        self.assertEqual(checks["local hook implementation present"], "INFO")

    def test_warns_when_required_foundation_signals_are_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            checks = {name: (status, required) for name, status, required in AUDIT.audit_repo(directory)}

        self.assertEqual(checks["CI workflow"], ("WARN", True))
        self.assertEqual(checks["test files"], ("WARN", True))
        self.assertEqual(checks["test strategy: integration"], ("WARN", True))

    def test_covered_layer_needs_existing_test_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "README.md").write_text(
                "## Test Strategy\n| Unit | Covered | `tests/missing_test.py` |", encoding="utf-8"
            )
            statuses = AUDIT.test_strategy_status(repo, {"README.md": repo / "README.md"})

        self.assertEqual(statuses["unit"], "WARN")


if __name__ == "__main__":
    unittest.main()
