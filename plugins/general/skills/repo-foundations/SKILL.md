---
name: repo-foundations
description: >-
  Establish or improve a repository's engineering foundations: project structure,
  coding standards, tests, CI, Git hooks, documentation, releases, and workspace
  hygiene, adapted to the technology and product risks.
---

# Repository Foundations

Apply this skill to the user's requested scope. Inspect existing conventions
first; preserve existing work and avoid speculative infrastructure.

## Rulesets

1. **Structure and discovery.** Follow ecosystem conventions, keep boundaries
   testable, localize user-facing text, and make important knowledge easy to
   find. Read [architecture and quality](references/architecture-and-quality.md)
   and [indexes and inventories](references/indexes-and-inventories.md). Read
   [agent instructions](references/agent-instructions.md) when creating or
   changing `AGENTS.md` or `CLAUDE.md`.
2. **Confidence and enforcement.** Assess relevant test layers for every
   feature; additions, changes, and removals must keep tests and any maintained
   indexes aligned.
   Put fast checks in pre-push and deterministic authoritative gates in CI. Read
   [CI and release](references/ci-and-release.md).
3. **Operations and protection.** Make setup, data, performance, telemetry,
   publication, and cleanup reproducible and safe for the product. Read
   [operations and hygiene](references/operations-and-hygiene.md) and the CI
   reference for delivery rules.
4. **Roadmaps.** For multi-step work, create and maintain a staged roadmap with
   explicit outcomes, dependencies, acceptance checks, and parallelizable
   tasks. Follow [roadmap guidance](references/roadmaps.md).

## Workflow

1. Inspect product constraints, source layout, tests, docs, toolchain, hooks, CI,
   release process, and current risks. Ask only about decisions that materially
   change the solution.
2. Select applicable rulesets; record justified N/A decisions. Avoid adding
   indexes or tools that do not improve navigation or repeatability.
3. Implement the smallest coherent change. Update callers, tests, relevant
   maintained indexes, and canonical docs together. Automate repeated tasks
   with tested helpers and keep a canonical developer-tool index of purpose,
   prerequisites, and invocation.
4. Map each applicable rule to a test, pre-push check, CI gate, or human review.
   Test the enforcement wiring. Keep slow/device suites out of pre-push; CI
   remains authoritative if hooks are missing or bypassed.
5. Run `python <skill-dir>/scripts/foundations_audit.py <repo>` as a heuristic
   gap check, then run relevant project checks. Verify remote CI before claiming
   a push is green. Report failures, skips, assumptions, and unverified support.

## Safety

Never publish secrets, personal files, private exports, screenshots, local
databases, machine-specific configuration, or sensitive identifiers without
authorization. Review staged content and artifacts; require Gitleaks or an
equivalent in CI and the installed pre-push hook. Keep exceptions narrow,
owned, and time-bounded. If a credential is exposed, revoke/rotate it; removing
the text alone is insufficient.

Use `python <skill-dir>/scripts/repo_check.py <repo>` for a read-only status,
worktree, and staged-filename inventory; it does not inspect content or certify
publication safety. Remove only task-created temporary files. Before removing a
delegated worktree, verify it is inactive and clean, its commits are retained,
and ignored/untracked data is inspected and preserved or explicitly authorized
for removal. Use `git worktree prune --dry-run` before pruning metadata. Delete
branches only with authorization and after verifying commit retention. Never
remove unrelated user changes, caches, branches, or worktrees.
