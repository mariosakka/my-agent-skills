---
name: repo-foundations
description: >-
  Establish or improve a repository's engineering foundations: project structure,
  coding standards, tests, CI, Git hooks, documentation, releases, and workspace
  hygiene, adapted to the technology and product risks.
---

# Repository Foundations

Use this skill when asked to create a repository or establish its engineering
standards. Preserve the user's requested scope and existing work; do not add
infrastructure or change deployment policy merely because it appears below.

## Workflow

1. Inspect the repository, any existing instructions, toolchain, tests, CI,
   release and documentation practices before changing them. Establish the
   product type, users, supported platforms, data sensitivity, and deployment
   needs. Ask only when an unresolved decision materially changes the result.
2. Reuse local patterns and the language/framework's standard tools. Choose
   boundaries, naming, and tests for this project rather than copying another
   stack's architecture. Read [architecture and quality](references/architecture-and-quality.md)
   for structure, documentation, and risk-based test decisions.
3. For CI, hooks, publication, or release work, read
   [CI and release](references/ci-and-release.md). A local hook is advisory;
   the corresponding required CI gate must not depend on its installation.
   Prefer platform-neutral developer checks; when supported contributors need
   different shells, provide tested native equivalents and document their parity.
4. Implement the requested foundations with the fewest files and dependencies
   that cover the real needs. Include runnable checks for new behavior, update
   the actual callers and canonical docs, and run the relevant checks. Report
   failures, skipped checks, assumptions, and unverified platform support.
   Every feature change must add or update related tests; feature removals must
   remove or rewrite tests for behavior that no longer exists. Assess each test
   layer and record coverage or a reasoned N/A in the plan/PR.
5. Run `python <skill-dir>/scripts/foundations_audit.py <repo>` to check
   observable repository foundations and identify gaps. Treat heuristic results
   as prompts for review, not proof of quality; architecture and risk decisions
   still require human judgment. Establish a small, reusable developer-tooling
   set for recurring project tasks. Index each script/tool and its purpose and invocation in the canonical
   developer entrypoint (for example, `make help`, `just --list`, or
   `docs/development.md`). As work proceeds, actively look for repeated or
   error-prone development, test, CI, and release steps that are worth
   automating; add deterministic, tested helpers when they materially improve
   reliability or reduce toil. Prefer extending an existing task runner or
   script over adding duplicate wrappers, and do not create placeholder tools
   just to satisfy this baseline.

## Privacy And Workspace Safety

Never commit or publish secrets, personal files, private exports, screenshots,
local databases, machine-specific configuration, or sensitive identifiers
without explicit authorization. Use sanitized fixtures and appropriate ignore
rules. Before committing or publishing, review the actual staged diff and
artifacts, including contents and history when relevant; use an established
secret scanner if available. Filename checks alone cannot prove safety. If
ownership or sensitivity is unclear, leave the item out and ask.

For a read-only inventory, run `python <skill-dir>/scripts/repo_check.py <repo>`.
It reports Git status, worktrees, and suspicious staged filenames; it does not
inspect content, scan history, or guarantee that a commit is safe to publish.
Review its warnings and Git's actual staged diff before any publication.

Clean up temporary files created by the task. Close delegated agents and inspect
their worktrees; remove a worktree only after verifying it is inactive, clean,
its commits are retained, and ignored/untracked files have been inspected and
preserved or their removal explicitly authorized. Delete a branch only with
authorization and after verifying its commits are retained. Never remove unrelated user files, caches,
worktrees, branches, or uncommitted changes. Use `git worktree prune --dry-run`
before pruning stale metadata, and report anything that cannot be safely cleaned.
