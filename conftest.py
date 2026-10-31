"""Shared fixtures for the skill tests.

Everything that would touch the network or a real account (`gh`, Slack, ...) is replaced by a stub
executable placed first on PATH, so the shell scripts run for real against canned responses.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
PLUGINS = REPO / "plugins"


def _find_bash():
    candidates = [shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"]
    for c in candidates:
        if c and "system32" not in c.lower().replace("/", "\\") and os.path.exists(c):
            return c  # the WSL launcher in System32 is not a usable bash
    return None


BASH = _find_bash()


def skill_dirs():
    return sorted(p.parent for p in PLUGINS.glob("*/skills/*/SKILL.md"))


@pytest.fixture
def tmp_path():
    """Plain mkdtemp dir: pytest's own tmp_path root can be unreadable (permissions) on some machines."""
    d = Path(tempfile.mkdtemp(prefix="skilltest-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def bash():
    if not BASH:
        pytest.skip("bash not available")
    return BASH


@pytest.fixture(scope="session")
def need_jq():
    if not shutil.which("jq"):
        pytest.skip("jq not available")


def _jq_needs_shim():
    """A native Windows jq.exe cannot open bash's /proc/<pid>/fd/N (`jq ... <(cmd)`)."""
    if not (BASH and shutil.which("jq")):
        return False
    r = subprocess.run([BASH, "-c", "jq -s add <(echo '[1]')"], capture_output=True, text=True)
    return r.returncode != 0


JQ_NEEDS_SHIM = _jq_needs_shim()


class FakeBin:
    """A directory of stub executables that is prepended to PATH."""

    def __init__(self, root: Path):
        self.dir = root / "fakebin"
        self.dir.mkdir()
        self.log = root / "calls.log"
        self.log.write_text("")
        self._n = 0
        if JQ_NEEDS_SHIM:  # copy process-substitution files to real temp files before calling the real jq
            real = Path(shutil.which("jq")).as_posix()
            self._write("jq", f'''#!/usr/bin/env bash
args=(); tmp=()
for a in "$@"; do
  case "$a" in
    /proc/*/fd/*|/dev/fd/*) t=$(mktemp); cat "$a" > "$t"; tmp+=("$t"); args+=("$t");;
    *) args+=("$a");;
  esac
done
"{real}" "${{args[@]}}"; rc=$?
rm -f "${{tmp[@]}}"
exit $rc
''')

    def _write(self, name, text):
        p = self.dir / name
        p.write_text(text, newline="\n")
        p.chmod(0o755)

    def gh(self, routes):
        """routes: list of (bash glob matched against "$*", stdout, exit code). First match wins."""
        body = ['#!/usr/bin/env bash', f'echo "$*" >> "{self.log.as_posix()}"']
        for pattern, out, code in routes:
            self._n += 1
            f = self.dir / f"out{self._n}.txt"
            f.write_text(out, encoding="utf-8", newline="\n")
            body.append(f'case "$*" in {pattern}) cat "{f.as_posix()}"; exit {code};; esac')
        body.append('echo "fake gh: no route for: $*" >&2; exit 99')
        self._write("gh", "\n".join(body) + "\n")

    def command(self, name, script="exit 0"):
        self._write(name, f"#!/usr/bin/env bash\n{script}\n")

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines()

    def env(self, **extra):
        env = dict(os.environ)
        env["PATH"] = str(self.dir) + os.pathsep + env["PATH"]
        env.update(extra)
        return env


@pytest.fixture
def fakebin(tmp_path):
    return FakeBin(tmp_path)


@pytest.fixture
def sh(bash):
    """run(script, *args, cwd=None, env=None, stdin=None) -> CompletedProcess (text, utf-8)."""

    def run(script, *args, cwd=None, env=None, stdin=None):
        return subprocess.run([bash, Path(script).as_posix(), *map(str, args)], cwd=cwd, env=env, input=stdin,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    return run


@pytest.fixture
def py():
    """run(script, *args, cwd=None, env=None) -> CompletedProcess for a Python script."""

    def run(script, *args, cwd=None, env=None, stdin=None):
        return subprocess.run([sys.executable, str(script), *map(str, args)], cwd=cwd, env=env, input=stdin,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)

    return run


GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


@pytest.fixture
def git_repo(tmp_path):
    """git(*args, when=None) runs git in a fresh repo whose default branch is `development`; `when` = unix time of the commit."""
    if not shutil.which("git"):
        pytest.skip("git not available")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args, when=None):
        env = {**os.environ, **GIT_ENV}
        if when is not None:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = f"{int(when)} +0000"
        r = subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        return r.stdout

    git.path = repo
    git.commit = lambda name, when=None: (((repo / name).write_text(name)), git("add", name), git("commit", "-m", name, when=when))
    git.now = time.time
    git("init", "-b", "development")
    git.commit("base.txt", when=time.time() - 100 * 3600)
    return git
