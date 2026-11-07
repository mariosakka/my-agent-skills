# CI, Hooks, And Releases

## CI And Hooks

Document a reproducible local gate and enforce its essential checks in CI:
formatting, lint/type analysis, relevant tests, builds, and whitespace checks
as appropriate. Pin toolchains and review dependencies. Give workflows minimum
permissions, isolate untrusted pull requests from secrets, and pin third-party
actions to reviewed immutable revisions where supported. Use concurrency limits,
timeouts, and caching without sharing mutable test state between parallel jobs.

Run Gitleaks or an equivalent secret scanner as a required CI check for pull
requests and pushes, plus a scheduled full-history scan. Wire the same pinned
scanner version and repository config into the installed pre-push hook, scanning
the outgoing commits before they leave the machine. CI remains authoritative;
the hook must fail with installation instructions when the scanner is missing,
not silently pass. Document narrow false-positive exceptions with owner, reason,
and expiry, and test that both CI and hook wiring remain present.

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

If a repository maintains a test index, enforce its two-way drift check in CI
and, where fast, pre-push. See [indexes and inventories](indexes-and-inventories.md)
for the consistency contract and when an index is worthwhile.

Prefer one platform-neutral task runner for developer checks. When a required
check depends on a shell or platform unavailable to supported contributors,
provide a native equivalent only where needed, keep both implementations
behaviorally aligned, and add parity tests or shared fixtures to detect drift.
Document the canonical CI command and each supported local invocation.

For applications with user-facing text, validate localization catalogs and
generated accessors in CI: parse/generate catalogs, detect missing or extra
keys and placeholder mismatches, run locale/fallback/message-format tests, and
run the stack's hard-coded-visible-string lint where available. Add a fast
changed-project version of these checks to pre-push when practical; keep CI
authoritative and provide a documented reasoned N/A only for products without
user-facing copy. Keep an enforcement matrix in contributor docs that maps each
automatable skill rule to its CI job and/or hook, and names manual review for
rules that cannot be checked deterministically. Do not claim a rule is enforced
merely because a script exists: test that CI and installed hooks invoke it.

For performance benchmarks, retain machine-readable or clearly structured
results with the tested commit/build, scenario, device or runner tier, OS,
configuration, run count, and measured values. Link CI artifacts to the
maintained performance ledger and compare like-for-like baselines. For
device-sensitive apps, cover both a current reference tier and an older or
lowest-supported physical device; use emulators for repeatable screening, not
as a substitute for hardware evidence. Avoid hard CI thresholds until the
measurement is stable and calibrated; once adopted, document the budget and
alert/failure policy.

## API Contracts And Publication

- Choose and document one source of truth for the public API contract (for
  example OpenAPI, protobuf, or GraphQL schema). Pin the generator/toolchain and
  make generation deterministic. State whether generated clients/schemas are
  committed or built as release artifacts; do not hand-edit generated output.
- In CI, validate and lint the contract, regenerate artifacts and fail on
  unexplained drift, run endpoint contract tests, and check changes against the
  last released contract for breaking compatibility. Build representative
  generated clients or consumer fixtures so a valid schema that produces
  unusable clients cannot pass unnoticed.
- Publish versioned, immutable schemas and generated clients from a protected
  release ref only after required tests pass. Keep artifact versioning aligned
  with the API compatibility policy; document deprecation, migration, and
  support windows. Publishing API documentation/contracts is distinct from
  deploying the API service.
- For API service deployment, promote the same tested image/artifact through
  staging and production, run health and contract smoke checks against the
  deployed version, protect production credentials and approvals, and define a
  rollback path that accounts for database migrations. Never deploy from an
  untrusted pull-request job or expose internal routes in public API docs.
- Verify publication and deployment through the registry/endpoint and record
  the source commit, artifact version/checksum, and workflow run. A configured
  workflow or a successful build alone is not proof that the contract or API
  was actually published. Repositories without an API should record this layer
  as not applicable rather than adding unused release infrastructure.

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
- Release Please PRs may be created by `GITHUB_TOKEN`, whose PR-triggered
  workflows can require approval. Explicitly dispatch the normal full CI for the
  exact release branch, then enable auto-merge only after success and only if
  the PR head SHA still matches the validated SHA. Restrict the merge workflow
  to the expected bot and release branch; never use admin bypass or merge on an
  unverified release PR.
- A branch ruleset that requires a named check on the PR head is not satisfied
  by a run dispatched on the default branch, and bot pushes do not trigger the
  `pull_request` run. After the exact-SHA validation passes, have the merge job
  post a commit status with the required context on that same SHA (grant
  `statuses: write` at job level) before merging, and test that order.
- In `pull_request` jobs diff against the commit that was actually checked out
  (`git rev-parse HEAD`), not `$GITHUB_SHA`. The event's merge commit goes stale
  when the base branch moves or the PR is closed and reopened, so a re-run or a
  reopen fails with `bad object` while the checkout holds a newer merge commit.
  Reopening a PR cannot repair this: it creates yet another merge commit.
- A release PR merged with `GITHUB_TOKEN` does not fire the release workflow's
  `push` trigger, so the tag and GitHub release are silently never created.
  Give the release workflow a `workflow_dispatch` trigger (dispatch is exempt
  from that rule) and have the merge job run `gh workflow run <release>.yml
  --ref <default-branch>` right after merging (`actions: write` at job level).
  Verify with `gh release list` after the first real release; a version bump on
  the default branch without a tag is the symptom.

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
