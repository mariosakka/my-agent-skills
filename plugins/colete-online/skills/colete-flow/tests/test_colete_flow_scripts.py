import shutil
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
H = 3600


def test_board_lists_issues_and_defaults_to_platform_repo(sh, fakebin, tmp_path):
    fakebin.gh([("issue*list*", "#12  Fix login  [bug]\n#13  Add export  []\n", 0)])
    r = sh(SCRIPTS / "co-board.sh", env=fakebin.env())
    assert r.returncode == 0
    assert "=== Open unassigned issues in Colete-Online/platform ===" in r.stdout
    assert "#12  Fix login  [bug]" in r.stdout
    call = fakebin.calls()[0]
    assert "--repo Colete-Online/platform" in call and "--state open" in call and "--limit 10" in call


def test_board_accepts_owner_and_repo(sh, fakebin):
    fakebin.gh([("issue*list*", "", 0)])
    r = sh(SCRIPTS / "co-board.sh", "acme", "widgets", env=fakebin.env())
    assert "in acme/widgets" in r.stdout
    assert "--repo acme/widgets" in fakebin.calls()[0]


def test_branch_check_reports_ahead_and_staged(sh, git_repo):
    git_repo("checkout", "-b", "feature")
    git_repo.commit("a.txt")
    git_repo.commit("b.txt")
    (git_repo.path / "c.txt").write_text("c")
    git_repo("add", "c.txt")
    r = sh(SCRIPTS / "co-branch-check.sh", cwd=git_repo.path)
    assert r.returncode == 0, r.stdout
    assert "Branch  : feature" in r.stdout
    assert "Ahead of development : 2 commit(s)" in r.stdout
    assert "Behind development   : 0 commit(s)" in r.stdout
    assert "Branch is based on development" in r.stdout
    assert "Staged files:" in r.stdout and "c.txt" in r.stdout


def test_branch_check_counts_behind(sh, git_repo):
    git_repo("checkout", "-b", "feature")
    git_repo.commit("a.txt")
    git_repo("checkout", "development")
    git_repo.commit("dev1.txt")
    git_repo("checkout", "feature")
    r = sh(SCRIPTS / "co-branch-check.sh", cwd=git_repo.path)
    assert "Behind development   : 1 commit(s)" in r.stdout
    assert r.returncode == 1 and "does NOT descend from development" in r.stdout


def test_branch_check_fails_when_not_based_on_development(sh, git_repo):
    git_repo("checkout", "--orphan", "stray")
    git_repo.commit("x.txt")
    r = sh(SCRIPTS / "co-branch-check.sh", cwd=git_repo.path)
    assert r.returncode == 1
    assert "does NOT descend from development" in r.stdout


def _feature_branch(git_repo, hours_ago):
    git_repo("checkout", "-b", "feature")
    git_repo.commit("work.txt", when=time.time() - hours_ago * H - 60)


def estimate(sh, fakebin, git_repo, body):
    fakebin.gh([("issue*view*", body, 0)])
    return sh(SCRIPTS / "co-estimate-check.sh", "o/r", "7", cwd=git_repo.path, env=fakebin.env())


def test_estimate_requires_arguments(sh):
    r = sh(SCRIPTS / "co-estimate-check.sh")
    assert r.returncode != 0 and "Usage" in r.stderr


def test_estimate_warns_when_body_has_no_estimation(sh, fakebin, git_repo):
    r = estimate(sh, fakebin, git_repo, "Just a description\nNothing else\n")
    assert r.returncode == 0
    assert "No 'Estimation:' field found in issue #7 body" in r.stdout


def test_estimate_unknown_age_without_commits(sh, fakebin, git_repo):
    git_repo("checkout", "-b", "feature")
    r = estimate(sh, fakebin, git_repo, "Estimation: 8h\n")
    assert r.returncode == 0
    assert "Estimated: 8h" in r.stdout and "branch age unknown" in r.stdout


@pytest.mark.parametrize("hours_ago,estimate_h,code,message", [
    (1, 10, 0, "Within estimate (1h / 10h)"),
    (6, 10, 0, "Past 50% of estimate (6h / 10h)"),
    (12, 10, 1, "OVER ESTIMATE by 2h"),
])
def test_estimate_compares_elapsed_with_estimate(sh, fakebin, git_repo, hours_ago, estimate_h, code, message):
    _feature_branch(git_repo, hours_ago)
    r = estimate(sh, fakebin, git_repo, f"Some text\nEstimation: {estimate_h} hours\n")
    assert r.returncode == code, r.stdout
    assert message in r.stdout


def readiness(sh, fakebin, git_repo, *args):
    return sh(SCRIPTS / "co-pr-readiness.sh", *args, cwd=git_repo.path, env=fakebin.env())


def test_readiness_all_checks_pass(sh, fakebin, git_repo):
    fakebin.gh([("auth*", "", 0), ("api*user*", "octocat\n", 0)])
    fakebin.command("co-pr")
    r = readiness(sh, fakebin, git_repo, "acme/app", "42")
    assert r.returncode == 0, r.stdout
    assert "co-pr readiness check for acme/app" in r.stdout
    assert "Working tree clean" in r.stdout
    assert "Issue number: 42" in r.stdout
    assert "gh authenticated as: octocat" in r.stdout
    assert "ready to run: co-pr 42" in r.stdout


def test_readiness_fails_on_dirty_tree(sh, fakebin, git_repo):
    fakebin.gh([("auth*", "", 0), ("api*", "me\n", 0)])
    fakebin.command("co-pr")
    (git_repo.path / "dirty.txt").write_text("x")
    r = readiness(sh, fakebin, git_repo, "acme/app", "1")
    assert r.returncode == 1
    assert "Uncommitted changes present" in r.stdout and "Fix the above issues" in r.stdout


def test_readiness_fails_when_gh_not_authenticated(sh, fakebin, git_repo):
    fakebin.gh([("auth*", "", 1)])
    fakebin.command("co-pr")
    r = readiness(sh, fakebin, git_repo)
    assert r.returncode == 1
    assert "gh: not authenticated" in r.stdout
    assert "No issue number supplied" in r.stdout


def test_readiness_fails_without_co_pr(sh, fakebin, git_repo):
    if shutil.which("co-pr"):
        pytest.skip("a real co-pr is installed on this machine")
    fakebin.gh([("auth*", "", 0), ("api*", "me\n", 0)])
    r = readiness(sh, fakebin, git_repo, "acme/app", "1")
    assert r.returncode == 1 and "co-pr not found in PATH" in r.stdout
