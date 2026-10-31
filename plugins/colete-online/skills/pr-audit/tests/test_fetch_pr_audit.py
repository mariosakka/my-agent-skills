import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch-pr-audit.sh"
pytestmark = pytest.mark.usefixtures("need_jq")


def pr(number, assignees=(), body="", draft=False, reviews=(), requests=(), author="bot-account"):
    return {"number": number, "title": f"PR {number}", "url": f"https://x/pull/{number}", "author": {"login": author},
            "assignees": [{"login": a} for a in assignees], "isDraft": draft, "body": body,
            "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-02T00:00:00Z",
            "reviewRequests": [{"login": r} for r in requests],
            "reviews": [{"author": {"login": a}, "state": s} for a, s in reviews]}


def test_requires_mode_and_repo(sh, fakebin):
    r = sh(SCRIPT, "--mode", "authored", env=fakebin.env())
    assert r.returncode == 1 and "--mode and --repo are required" in r.stderr


def test_help_and_unknown_mode_and_unknown_arg(sh, fakebin):
    assert "Usage:" in sh(SCRIPT, "--help", env=fakebin.env()).stdout
    r = sh(SCRIPT, "--mode", "weird", "--repo", "o/r", "--user", "me", env=fakebin.env())
    assert r.returncode == 1 and "Unknown --mode 'weird'" in r.stderr
    r = sh(SCRIPT, "--nope", env=fakebin.env())
    assert r.returncode == 1 and "Unknown arg: --nope" in r.stderr


def test_to_review_shapes_the_listing(sh, fakebin):
    listing = [pr(5, requests=("me", "other"), reviews=[("coderabbitai", "COMMENTED")], author="alice", draft=True)]
    fakebin.gh([("pr*list*", json.dumps(listing), 0)])
    r = sh(SCRIPT, "--mode", "to-review", "--repo", "acme/app", "--user", "me", env=fakebin.env())
    assert r.returncode == 0, r.stderr
    [out] = json.loads(r.stdout)
    assert out["number"] == 5 and out["author"] == "alice" and out["isDraft"] is True
    assert out["reviewersRequested"] == ["me", "other"]
    assert out["reviewsAlreadyReceived"] == [{"login": "coderabbitai", "state": "COMMENTED"}]
    assert "review-requested:me" in fakebin.calls()[0] and "--repo acme/app" in fakebin.calls()[0]


def test_user_defaults_to_authenticated_gh_user(sh, fakebin):
    fakebin.gh([("api*user*", "octocat\n", 0), ("pr*list*", "[]", 0)])
    r = sh(SCRIPT, "--mode", "to-review", "--repo", "acme/app", env=fakebin.env())
    assert r.returncode == 0 and json.loads(r.stdout) == []
    assert any("review-requested:octocat" in c for c in fakebin.calls())


def authored(sh, fakebin, listing, extra_routes=(), **kw):
    routes = [("pr*list*", json.dumps(listing), 0), *extra_routes, ("api*graphql*", "0\n", 0)]
    fakebin.gh(routes)
    r = sh(SCRIPT, "--mode", "authored", "--repo", "acme/app", "--user", "me", *kw.get("args", ()), env=fakebin.env())
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_authored_includes_prs_assigned_to_the_user_only(sh, fakebin):
    out = authored(sh, fakebin, [pr(1, assignees=("me",)), pr(2, assignees=("someone",)), pr(3)])
    assert [p["number"] for p in out] == [1]


def test_authored_includes_prs_closing_an_issue_assigned_to_the_user(sh, fakebin):
    listing = [pr(1, assignees=("someone",), body="Fixes #77"), pr(2, body="Closes #88"), pr(3, body="no link")]
    routes = [("issue*view*77*", json.dumps({"assignees": [{"login": "me"}]}), 0),
              ("issue*view*88*", json.dumps({"assignees": [{"login": "other"}]}), 0)]
    out = authored(sh, fakebin, listing, routes)
    assert [p["number"] for p in out] == [1]


def test_authored_splits_bot_and_human_reviews_and_drops_own(sh, fakebin):
    reviews = [("coderabbitai", "COMMENTED"), ("dependabot[bot]", "APPROVED"), ("alice", "APPROVED"),
               ("me", "COMMENTED")]
    [out] = authored(sh, fakebin, [pr(1, assignees=("me",), reviews=reviews, requests=("bob",))])
    assert out["humanReviews"] == [{"login": "alice", "state": "APPROVED"}]
    assert [b["login"] for b in out["botReviews"]] == ["coderabbitai", "dependabot[bot]"]
    assert out["reviewersRequested"] == ["bob"]
    assert out["wasPutBackToDraft"] is False


def test_authored_flags_prs_put_back_to_draft(sh, fakebin):
    listing = [pr(1, assignees=("me",)), pr(2, assignees=("me",))]
    routes = [("api*graphql*num=2*", "1\n", 0)]
    out = authored(sh, fakebin, listing, routes)
    assert {p["number"]: p["wasPutBackToDraft"] for p in out} == {1: False, 2: True}


def test_out_file(sh, fakebin, tmp_path):
    fakebin.gh([("pr*list*", "[]", 0)])
    target = tmp_path / "o.json"
    r = sh(SCRIPT, "--mode", "to-review", "--repo", "a/b", "--user", "me", "--out", str(target), env=fakebin.env())
    assert r.returncode == 0 and r.stdout.strip() == ""
    assert "Wrote 0 PR(s)" in r.stderr and json.loads(target.read_text(encoding="utf-8")) == []
