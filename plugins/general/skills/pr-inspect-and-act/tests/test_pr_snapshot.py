import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pr-snapshot.sh"
pytestmark = pytest.mark.usefixtures("need_jq")

MAIN = {
    "title": "Add export", "body": "Adds CSV export.\n\nCloses #12 and related to #3.", "author": {"login": "alice"},
    "additions": 30, "deletions": 4, "changedFiles": 2, "labels": [{"name": "feature"}], "reviewRequests": [],
    "url": "https://x/pull/5", "statusCheckRollup": [{"name": "ci", "state": "SUCCESS"}],
    "files": [{"path": "src/a.py", "additions": 20, "deletions": 1}, {"path": "src/b.py", "additions": 10, "deletions": 3}],
}


def routes(main=MAIN):
    issue = {"number": 12, "title": "Need export", "state": "OPEN", "labels": [{"name": "approved"}], "body": "Users want CSV",
             "comments": [{"author": {"login": "bob"}, "body": "please"}]}
    return [
        ("pr*view*", json.dumps(main), 0),
        ("api*pulls/5/comments", json.dumps([{"path": "src/a.py", "line": 7, "user": {"login": "carol"}, "body": "nit"}]), 0),
        ("api*issues/5/comments", json.dumps([{"user": {"login": "dave"}, "body": "LGTM overall"}]), 0),
        ("api*pulls/5/reviews", json.dumps([{"state": "APPROVED", "user": {"login": "erin"}, "body": "ship it"}]), 0),
        ("issue*view*12*", json.dumps(issue), 0),
        ("issue*view*3*", json.dumps({**issue, "number": 3, "title": "Related"}), 0),
    ]


def snapshot(sh, fakebin, main=MAIN):
    fakebin.gh(routes(main))
    return sh(SCRIPT, "acme/app", "5", env=fakebin.env())


def test_requires_repo_and_number(sh):
    r = sh(SCRIPT)
    assert r.returncode != 0 and "Usage: pr-snapshot" in r.stderr


def test_prints_every_section_in_reading_order(sh, fakebin):
    r = snapshot(sh, fakebin)
    assert r.returncode == 0, r.stderr
    sections = ["=== PR #5 — acme/app ===", "--- Linked Issue(s) ---", "--- Summary ---", "--- Changed Files ---",
                "--- Reviews", "--- Inline Review Comments ---", "--- Issue-level Comments"]
    positions = [r.stdout.index(s) for s in sections]
    assert positions == sorted(positions)  # the linked issue is read before the diff


def test_extracts_linked_issues_from_the_body(sh, fakebin):
    r = snapshot(sh, fakebin)
    assert "Need export" in r.stdout and '"number": 12' in r.stdout and '"number": 3' in r.stdout
    assert "bob" in r.stdout  # issue comments are included
    calls = fakebin.calls()
    assert sum(c.startswith("issue view") for c in calls) == 2


def test_warns_when_no_issue_is_linked(sh, fakebin):
    r = snapshot(sh, fakebin, {**MAIN, "body": "No link here"})
    assert "(none found in PR body" in r.stdout
    assert not any(c.startswith("issue view") for c in fakebin.calls())


def test_formats_files_reviews_and_comments(sh, fakebin):
    out = snapshot(sh, fakebin).stdout
    assert "+20 -1  src/a.py" in out and "+10 -3  src/b.py" in out
    assert "[APPROVED] erin: ship it" in out
    assert "[src/a.py:7] carol: nit" in out
    assert "[dave] LGTM overall" in out
    summary = json.loads(out.split("--- Summary ---")[1].split("--- Changed Files ---")[0])
    assert summary["author"] == "alice" and summary["labels"] == ["feature"] and summary["ci"] == [{"name": "ci", "state": "SUCCESS"}]
