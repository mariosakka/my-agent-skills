# Operations And Hygiene

Lessons from running a mobile project with hooks, CI, devices and delegated
agents. Apply what fits the project.

## Git And CI

- **Secret scanning.** Run Gitleaks (or an equivalent) in PR/push CI, a
  scheduled full-history check, and the installed pre-push hook. Pin the scanner
  version/config; fail clearly when a local hook dependency is missing. Keep
  allowlists narrow, reviewed, owned, and time-bounded. A finding blocks
  publication until the credential is revoked/rotated; removing it from the
  latest file does not remove exposure from Git history.
- **Executable bits.** Every tracked script is mode 100755 in the index; check
  it in CI or an audit script. A script committed as 100644 exits 126 in CI while
  a Windows hook runs it fine. Fix with `git update-index --chmod=+x`;
  `scripts/foundations_audit.py` reports tracked shebang scripts that lack it.
- **Verify CI after a push.** Do not report "pushed" or "green" until the
  workflow result for that commit has been read (`gh run list`, `gh run watch`).
  Provide a one-command check in the developer tooling.
- **Skipped is not passed.** An all-skipped contract or device run is a finding:
  record the reason and surface the skips in the workflow summary. Parse the test
  count from the reporter CI actually uses; a local format may differ.
- **Line endings.** Add `.gitattributes` (`text eol=lf` for scripts and hooks).
  `sed -i` and editors can silently rewrite a whole tree on Windows; renormalize
  in one dedicated commit.
- **Guard detection.** `foundations_audit.py` accepts any `scripts/` or `tools/`
  `check_*` script named for sync, updated or lifecycle that mentions tests and is
  referenced from CI or a hook; the name need not be `check_docs_sync.py`.
- **Per-commit policy gates.** Docs-with-code and tests-with-code checks shared
  by the hook and CI, with a visible opt-out trailer such as
  `Docs: n/a (reason)` instead of silent bypasses. Expect them to reject merged
  agent commits that lack docs.
- **Staging.** `git add -A` after tooling runs picks up generated files and large
  traces. Add an ignore rule when adding the tool that writes a new output folder.
- **Scheduled live checks.** Alert when they stop producing evidence, not only
  when they fail.

## Registers And Audits As Code

Keep an issue register with a format test, a stage-end audit script of greppable
checks, a recurring-issues checklist, and a test-count drift check. Link each
accepted limit to a reason and a recheck trigger.

## Reproducible Environments And Seed Data

- Document a clean-machine setup with exact prerequisites and one canonical
  command for starting required local services and running checks.
- Turn repeated setup, migration, seed, reset, and teardown steps into small
  scripts or task-runner commands with validated inputs, safe defaults, clear
  exit codes, and no embedded secrets. Keep them idempotent where practical,
  test their failure paths, and list their purpose and exact invocation in the
  canonical developer-tool index; do not leave important setup as a long manual
  command sequence.
- Use Docker Compose or an equivalent only when local infrastructure (such as
  a database, cache, or queue) materially improves reproducibility. Pin service
  versions, add readiness/health checks, use non-production credentials, and
  document start, reset, and teardown commands. Do not add containers just to
  satisfy a checklist when the project has no such dependency.
- Keep schema migrations and seed data separate. Seeds should be deterministic,
  repeatable, synthetic or sanitized, and safe to rerun. Require an explicit
  local/test environment guard; never seed production automatically or commit
  private/customer data. Document how test fixtures differ from developer demo
  data and how both are reset.
- Test the documented bootstrap and seed commands from a clean environment,
  including failure when required services are unavailable. Keep secrets in
  ignored local env files or a secret manager, with a committed example file
  containing placeholders only.

## Telemetry And User-Submitted Bug Reports

- Treat product telemetry and an explicit support/bug report as separate data
  flows. Document purpose, consent/opt-out, collected fields, retention,
  access, deletion, and the destination before enabling either in production.
- Collect the minimum useful diagnostics (for example app/build version,
  platform/OS, device model, and a sanitized error category). Strip tokens,
  credentials, personal identifiers, URLs with sensitive query data, and user
  content by default. Capture screenshots or logs only after a clear user action
  and consent; provide a preview/redaction path where feasible.
- Route repository issue creation through a trusted backend or narrowly scoped
  GitHub App. Never ship repository-write credentials in a client. Validate and
  size-limit payloads, rate-limit abuse, and keep an audit trail without
  retaining unnecessary report content.
- Make submission retry-safe with an idempotency key. Deduplicate on the
  server using a stable fingerprint of normalized issue category and sanitized
  diagnostic signature, not title text alone. Preserve distinct reports when
  meaningful context differs; add new evidence to an existing issue rather
  than silently discarding it. Return the created/existing issue reference and
  define retry/queue behavior when GitHub is unavailable.
- Test redaction, consent and opt-out, payload validation, rate limits,
  deduplication versus distinct reports, retries, and GitHub/API failure paths
  with fakes. Do not require a live repository write in ordinary CI.

## Accidental Publication

When private data reaches a remote: take a backup bundle, get explicit approval,
rewrite with `filter-repo` or `filter-branch`, verify that commit count and
subjects match, map old to new hashes and fix documents that cite them, push with
`--force-with-lease`, and remember that hosts and forks cache old objects.

## Devices And Performance

- Run a preflight (device attached, battery, storage, screen state) first.
- Restore every changed device setting in a trap.
- Confirm a setting took effect (measured frame rates, reported power state)
  instead of trusting the command that set it.
- Remove data that performance runs leave behind before functional runs.

## Delegated Agents

One actor per physical device. Give docs-only agents no device access. Check each
agent's claim against its diff. Expect merge conflicts in shared docs and tables.
Remove a worktree only after the merge is verified; Windows may keep an empty
folder busy.

## Mobile Signing

Keep signing keys and their properties files out of Git. Document the cost of
moving installed copies from debug to release or store signing (data loss unless
exported first), and check that no release workflow falls back to debug signing.
