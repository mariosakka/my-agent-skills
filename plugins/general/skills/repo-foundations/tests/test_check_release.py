from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release.py"


class CheckReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        (self.repo / "tracked file.txt").write_text("first", encoding="utf-8")
        self.git("add", "--", "tracked file.txt")
        self.git("commit", "-qm", "first")
        self.commit = self.git("rev-parse", "HEAD").decode().strip()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def check(self, tag="v1", commit=None, repo=None):
        before = (self.git("status", "--porcelain=v1", "-z", "--untracked-files=all"),
                  self.git("show-ref", "--head"), (self.repo / ".git" / "index").read_bytes())
        result = subprocess.run([sys.executable, str(SCRIPT), str(repo or self.repo), tag,
                                 commit if commit is not None else self.commit],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        after = (self.git("status", "--porcelain=v1", "-z", "--untracked-files=all"),
                 self.git("show-ref", "--head"), (self.repo / ".git" / "index").read_bytes())
        self.assertEqual(before, after)
        return result

    def test_lightweight_and_annotated_tags(self):
        self.git("tag", "v1")
        self.git("tag", "-a", "v2", "-m", "release")
        for tag in ("v1", "v2"):
            with self.subTest(tag=tag):
                result = self.check(tag)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("working tree is clean", result.stdout)

    def test_missing_and_mismatched_tags(self):
        self.assertEqual(self.check().returncode, 1)
        self.git("tag", "v1")
        result = self.check(commit="0" * len(self.commit))
        self.assertEqual(result.returncode, 1)
        self.assertIn("mismatch", result.stdout)

    def test_dirty_tracked_and_untracked_files(self):
        self.git("tag", "v1")
        (self.repo / "tracked file.txt").write_text("changed", encoding="utf-8")
        (self.repo / "untracked file.txt").write_text("new", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("dirty", result.stdout)

    def test_clean_checkout_at_another_commit_fails(self):
        self.git("tag", "v1")
        (self.repo / "tracked file.txt").write_text("second", encoding="utf-8")
        self.git("add", "--", "tracked file.txt")
        self.git("commit", "-qm", "second")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checkout commit mismatch", result.stdout)

    def test_invalid_arguments_and_git_error(self):
        self.assertEqual(self.check(commit="HEAD").returncode, 2)
        self.assertEqual(self.check(tag="-invalid").returncode, 2)
        result = self.check(repo=self.repo / "missing")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Git error", result.stderr)

    def test_inherited_git_dir_cannot_redirect_check(self):
        self.git("tag", "v1")
        with tempfile.TemporaryDirectory() as other:
            subprocess.run(["git", "init", "-q", other], check=True)
            env = os.environ.copy()
            env["GIT_DIR"] = str(Path(other) / ".git")
            result = subprocess.run([sys.executable, str(SCRIPT), str(self.repo),
                                     "v1", self.commit], capture_output=True,
                                    text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
