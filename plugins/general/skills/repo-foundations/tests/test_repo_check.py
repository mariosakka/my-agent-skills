from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "repo_check.py"


class RepoCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def check_repo(self, path=None):
        return subprocess.run([sys.executable, str(SCRIPT), str(path or self.repo)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_sensitive_and_ordinary_staged_paths_do_not_mutate_repo(self):
        for name in ("normal file.txt", "my private_key.pem", ".env.local", "backup.p12"):
            (self.repo / name).write_text("secret content must not appear", encoding="utf-8")
        self.git("add", "--", "normal file.txt", "my private_key.pem", ".env.local", "backup.p12")
        before = self.git("status", "--porcelain=v1", "-z")
        index = (self.repo / ".git" / "index").read_bytes()
        result = self.check_repo()
        self.assertEqual(result.returncode, 1, result.stderr)
        for name in ("normal file.txt", "my private_key.pem", ".env.local", "backup.p12"):
            self.assertIn(name, result.stdout)
        self.assertNotIn("secret content", result.stdout + result.stderr)
        self.assertIn("Worktrees:", result.stdout)
        self.assertIn("incomplete", result.stdout)
        self.assertEqual(before, self.git("status", "--porcelain=v1", "-z"))
        self.assertEqual(index, (self.repo / ".git" / "index").read_bytes())

    def test_ordinary_staged_file_succeeds(self):
        (self.repo / "read me.txt").write_text("hello", encoding="utf-8")
        self.git("add", "--", "read me.txt")
        result = self.check_repo()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("read me.txt", result.stdout)
        self.assertIn("None identified", result.stdout)

    def test_invalid_repository_is_an_error(self):
        result = self.check_repo(self.repo / "missing")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Git error", result.stderr)

    def test_inherited_git_dir_cannot_redirect_inspection(self):
        (self.repo / ".env").write_text("private", encoding="utf-8")
        self.git("add", "--", ".env")
        with tempfile.TemporaryDirectory() as other:
            subprocess.run(["git", "init", "-q", other], check=True)
            env = os.environ.copy()
            env["GIT_DIR"] = str(Path(other) / ".git")
            result = subprocess.run([sys.executable, str(SCRIPT), str(self.repo)],
                                    capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(".env", result.stdout)


if __name__ == "__main__":
    unittest.main()
