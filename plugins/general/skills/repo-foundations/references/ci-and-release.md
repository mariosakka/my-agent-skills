# CI, Hooks, And Releases

## CI And Hooks

Document a reproducible local gate and enforce its essential checks in CI:
formatting, lint/type analysis, relevant tests, builds, and whitespace checks
as appropriate. Pin toolchains and review dependencies. Give workflows minimum
permissions, isolate untrusted pull requests from secrets, and pin third-party
actions to reviewed immutable revisions where supported. Use concurrency limits,
timeouts, and caching without sharing mutable test state between parallel jobs.

Keep fast deterministic checks on pull requests; separate expensive device,
performance, live-contract, and scheduled checks. Confirm required jobs execute
non-empty test selections. For documentation-only changes, skip functional
tests only when classification reliably excludes executable changes; keep docs
and applicable quality checks. Provide an optional, documented hook installer
for fast feedback. CI is authoritative because local hooks can be bypassed.

Enforce feature/test lifecycle alignment in local hooks and CI: source additions
or edits require related test additions or updates; source removals require
obsolete tests to be updated or removed; standalone test deletion requires a
documented reason. Provide a narrow reasoned bypass for changes where tests are
not applicable.

Prefer one platform-neutral task runner for developer checks. When a required
check depends on a shell or platform unavailable to supported contributors,
provide a native equivalent only where needed, keep both implementations
behaviorally aligned, and add parity tests or shared fixtures to detect drift.
Document the canonical CI command and each supported local invocation.

## Dependency-Update Automation

Configure an update bot such as Dependabot or Renovate for the repository's
actual manifests and GitHub Actions. Group compatible updates where review is
still clear, set a sensible cadence, and keep security updates visible. Check
that lockfiles and generated dependency metadata are included. A bot config is
not evidence that updates are healthy: verify a real pull request and its
workflow runs.

Auto-merge only patch and minor bot updates; leave major bumps (including
GitHub Actions majors) for a human. Merge only after the required checks passed
on the exact head commit (`--match-head-commit`), and treat a failed or
cancelled check as "leave open", not "retry blindly".

- Prefer native auto-merge plus branch protection. If protection is unavailable
  (for example a private repo on a free plan), `gh pr merge --auto` and the
  repo setting may do nothing; use a small workflow that polls the required
  workflows for the head SHA and then merges, and record the gap as a known
  issue.
- Bot PRs get a read-only token and no secrets under `pull_request`. Use
  `pull_request_target` only for metadata and merge, never check out or run PR
  code, give write scope at job level only, pin actions to full SHAs, set
  `timeout-minutes`, and filter on the bot's login. Read update type from a
  pinned metadata action, not from the PR title.
- Bot branches go stale after a CI or config fix lands on the default branch:
  the PR still carries the old result. Rebase through the bot's own mechanism
  or let it do so; do not merge on an old green run.
- Commit-message, docs and test-with-code policy gates must skip or exempt bot
  commits, or every dependency PR fails for a reason a bot cannot fix.
- Check the automation against real PRs before claiming it works; a workflow
  that was never triggered is untested.

## Build And Deployment Pipelines

Design separate, reviewable steps for validation, artifact build, signing,
publication, and deployment. Build once and promote the same immutable artifact
between tracks/environments when the platform supports it; record its source
commit and checksum. Protect production credentials with environment approval
and least privilege, keep secrets out of fork/pull-request jobs, and make
rollback or halt procedures executable and tested. A release-note/tag workflow
does not itself build, upload, or deploy an artifact. Verify each pipeline on a
non-production target before claiming it is operational.

## Release

Distinguish application artifacts, libraries, containers, and deployment
targets; do not enable package publication for an app by default. Establish
version ownership, tag format, release notes, supported branch, artifact
provenance, and release owner. Use the ecosystem's standard release tools;
Release Please is an option when it fits, but verify its version updates against
the actual project and do not mistake release creation for deployment.

Separate build, signing, release publication, and deployment. Restrict signing
keys and publishing credentials, use least privilege, and protect production
promotion with appropriate review. Document and test staging, rollback or halt,
and post-release checks. Do not claim a platform, workflow, artifact, or release
is supported merely because configuration exists: report actual evidence.

For a local Git provenance check, run
`python <skill-dir>/scripts/check_release.py <repo> <tag> <full-commit-id>`.
It checks the local tag, checkout commit, and working-tree cleanliness only;
Git's clean status excludes ignored files. The check does not validate CI,
signatures, artifacts, remote tags, or deployment.
