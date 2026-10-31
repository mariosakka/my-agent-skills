# Operations And Hygiene

Lessons from running a mobile project with hooks, CI, devices and delegated
agents. Apply what fits the project.

## Git And CI

- **Executable bits.** Every tracked script is mode 100755 in the index; check
  it in CI or an audit script. A script committed as 100644 exits 126 in CI while
  a Windows hook runs it fine. Fix with `git update-index --chmod=+x`.
- **Verify CI after a push.** Do not report "pushed" or "green" until the
  workflow result for that commit has been read (`gh run list`, `gh run watch`).
  Provide a one-command check in the developer tooling.
- **Skipped is not passed.** An all-skipped contract or device run is a finding:
  record the reason and surface the skips in the workflow summary. Parse the test
  count from the reporter CI actually uses; a local format may differ.
- **Line endings.** Add `.gitattributes` (`text eol=lf` for scripts and hooks).
  `sed -i` and editors can silently rewrite a whole tree on Windows; renormalize
  in one dedicated commit.
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
