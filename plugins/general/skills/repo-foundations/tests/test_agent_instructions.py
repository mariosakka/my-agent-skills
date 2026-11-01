from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_agent_instructions.py"


class AgentInstructionCheckTests(unittest.TestCase):
    def run_check(self, repo):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(repo)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_accepts_three_hundred_lines_and_valid_relative_links(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "docs").mkdir()
            (repo / "docs" / "policy.md").write_text("policy", encoding="utf-8")
            (repo / "AGENTS.md").write_text(
                "[Policy](docs/policy.md)\n" + "rule\n" * 299,
                encoding="utf-8",
            )

            result = self.run_check(repo)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("max 300 lines", result.stdout)

    def test_rejects_instruction_files_over_the_line_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "CLAUDE.md").write_text("rule\n" * 301, encoding="utf-8")

            result = self.run_check(repo)

        self.assertEqual(result.returncode, 1)
        self.assertIn("301 lines exceeds 300", result.stdout)

    def test_rejects_broken_local_links(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "AGENTS.md").write_text("[Missing](docs/missing.md)\n", encoding="utf-8")

            result = self.run_check(repo)

        self.assertEqual(result.returncode, 1)
        self.assertIn("broken local link: docs/missing.md", result.stdout)

    def test_rejects_links_that_escape_the_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("[Outside](../outside.md)\n", encoding="utf-8")

            result = self.run_check(repo)

        self.assertEqual(result.returncode, 1)
        self.assertIn("link escapes repository", result.stdout)

    def test_reports_no_instruction_files_without_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_check(Path(directory))

        self.assertEqual(result.returncode, 0)
        self.assertIn("no AGENTS.md or CLAUDE.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
