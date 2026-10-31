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

Prefer one platform-neutral task runner for developer checks. When a required
check depends on a shell or platform unavailable to supported contributors,
provide a native equivalent only where needed, keep both implementations
behaviorally aligned, and add parity tests or shared fixtures to detect drift.
Document the canonical CI command and each supported local invocation.

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
