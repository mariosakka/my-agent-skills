import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch-candidates.sh"
pytestmark = pytest.mark.usefixtures("need_jq")


def issue(number, labels=("approved",), assignees=(), state="OPEN", title=None):
    return {"number": number, "title": title or f"Issue {number}", "url": f"https://x/{number}",
            "labels": [{"name": n} for n in labels], "assignees": [{"login": a} for a in assignees],
            "body": f"body {number}", "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-02T00:00:00Z",
            "state": state}


LISTING = [
    issue(1),
    issue(2, labels=("approved", "bug")),
    issue(3, assignees=("sam",)),
    issue(4, labels=("bug",)),
    issue(5, labels=("approved", "bug"), assignees=("sam",)),
]


def run_plain(sh, fakebin, *args, listing=LISTING):
    fakebin.gh([("issue*list*", json.dumps(listing), 0)])
    r = sh(SCRIPT, *args, env=fakebin.env())
    return r, (json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None)


def numbers(out):
    return [i["number"] for i in out]


def test_default_is_approved_and_unassigned(sh, fakebin):
    r, out = run_plain(sh, fakebin)
    assert r.returncode == 0, r.stderr
    assert numbers(out) == [1, 2]
    assert "--state open" in fakebin.calls()[0]


def test_include_assigned_keeps_assigned_issues(sh, fakebin):
    _, out = run_plain(sh, fakebin, "--include-assigned")
    assert numbers(out) == [1, 2, 3, 5]


def test_multiple_labels_must_all_be_present(sh, fakebin):
    _, out = run_plain(sh, fakebin, "--label", "approved", "--label", "bug")
    assert numbers(out) == [2]
    _, out = run_plain(sh, fakebin, "--label", "bug", "--include-assigned")
    assert numbers(out) == [2, 4, 5]


def test_repo_and_state_are_passed_to_gh(sh, fakebin):
    run_plain(sh, fakebin, "--repo", "acme/app", "--state", "all")
    call = fakebin.calls()[0]
    assert "--repo acme/app" in call and "--state all" in call


def test_out_file_is_written_and_stdout_stays_empty(sh, fakebin, tmp_path):
    target = tmp_path / "cands.json"
    r, _ = run_plain(sh, fakebin, "--out", str(target))
    assert r.stdout.strip() == ""
    assert "Wrote 2 candidate(s)" in r.stderr
    assert numbers(json.loads(target.read_text(encoding="utf-8"))) == [1, 2]


def test_output_objects_keep_expected_fields(sh, fakebin):
    _, out = run_plain(sh, fakebin)
    assert {"number", "title", "url", "labels", "body", "createdAt", "updatedAt"} <= set(out[0])


def test_help_and_bad_arguments(sh, fakebin):
    r = sh(SCRIPT, "--help", env=fakebin.env())
    assert r.returncode == 0 and "Plain mode" in r.stdout
    r = sh(SCRIPT, "--bogus", env=fakebin.env())
    assert r.returncode == 1 and "Unknown arg: --bogus" in r.stderr


def test_board_mode_requires_owner_and_project(sh, fakebin):
    r = sh(SCRIPT, "--board", env=fakebin.env())
    assert r.returncode == 1 and "--board requires --owner and --project" in r.stderr


BOARD = {"items": [
    {"status": "Todo", "assignees": [], "content": {"number": 10}},
    {"status": "Todo", "assignees": ["sam"], "content": {"number": 11}},
    {"status": "Done", "assignees": [], "content": {"number": 12}},
    {"status": "Todo", "content": {"number": 13}},
    {"status": "Todo", "assignees": [], "content": {"number": 14}},
    {"status": "Todo", "assignees": [], "content": {}},
]}


def board_gh(fakebin):
    fakebin.gh([
        ("project*item-list*", json.dumps(BOARD), 0),
        ("issue*view*10*", json.dumps(issue(10)), 0),
        ("issue*view*13*", json.dumps(issue(13, labels=("bug",))), 0),
        ("issue*view*14*", json.dumps(issue(14, state="CLOSED")), 0),
        ("issue*view*11*", json.dumps(issue(11)), 0),
    ])


def test_board_mode_filters_by_status_assignee_label_and_open_state(sh, fakebin):
    board_gh(fakebin)
    r = sh(SCRIPT, "--board", "--owner", "acme", "--project", "3", env=fakebin.env())
    assert r.returncode == 0, r.stderr
    assert numbers(json.loads(r.stdout)) == [10]  # 11 assigned, 12 wrong column, 13 wrong label, 14 closed
    assert "project item-list 3 --owner acme" in fakebin.calls()[0]


def test_board_mode_include_assigned_and_custom_status(sh, fakebin):
    board_gh(fakebin)
    r = sh(SCRIPT, "--board", "--owner", "acme", "--project", "3", "--include-assigned", env=fakebin.env())
    assert numbers(json.loads(r.stdout)) == [10, 11]


def test_board_mode_empty_column_returns_empty_array(sh, fakebin):
    board_gh(fakebin)
    r = sh(SCRIPT, "--board", "--owner", "acme", "--project", "3", "--status", "Nowhere", env=fakebin.env())
    assert r.returncode == 0 and json.loads(r.stdout) == []
