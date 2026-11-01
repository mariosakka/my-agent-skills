# Indexes And Inventories

Use indexes to make important repository knowledge easy to discover and keep
lists from becoming stale. Create them where they reduce repeated searching or
coordination; do not create an index for every directory or duplicate an
existing source of truth.

## Useful Indexes

Select the indexes that fit the repository:

- Features/modules: purpose, owner or boundary, entry points, dependencies, and
  links to the canonical design or implementation docs.
- Tests: test layers/suites, how to run them, and the behavior or risk each
  suite protects.
- Documentation and decisions: current operational docs and accepted decisions;
  distinguish current guidance from historical records.
- APIs/contracts: canonical schemas, generated clients, compatibility policy,
  and publication location.
- Developer tools and workflows: purpose, prerequisites, invocation, CI job,
  and relevant hook.
- Known issues: impact, severity, state, owner, workaround, and next review.
- Performance/optimizations: candidate or completed change, baseline, measured
  result, evidence, trade-offs, and recheck trigger.

Keep each topic's detailed records in one canonical location and make indexes
link to them. Prefer generating indexes from structured metadata or discovery
commands. If an index is maintained by hand, identify who updates it and add a
deterministic consistency check when practical.

## Test Index Consistency

When a repository keeps a test index, verify it against actual test discovery
in both directions:

- Every discovered test file or named suite is represented by the index.
- Every indexed test entry resolves to an existing test file or an explicitly
  documented suite/group; stale paths and removed suites fail the check.
- Adding, renaming, changing the organization of, or removing tests updates the
  index when needed. Editing the index also runs the check against current test
  discovery.

Run this drift check in CI. Add its fast form to pre-push where practical, and
ensure both test-tree changes and index changes trigger it. Generated indexes
should be regenerated in CI and compared with the committed result. Keep actual
test behavior and assertions in the test suite; an index is navigation and
coverage metadata, not a substitute for tests.

Do not impose a separate manually maintained test index on a small project if
test discovery and clear directory names already provide sufficient navigation.
If test coverage is instead recorded in a test strategy or feature matrix,
apply the same reciprocal drift principle to that canonical artifact.

`foundations_audit.py` reports heuristic signals for recognized test-index
filenames and drift-check references in CI/pre-push. This detects missing
wiring candidates; it does not execute or prove the repository's set-equality
check, which remains the project's responsibility.
