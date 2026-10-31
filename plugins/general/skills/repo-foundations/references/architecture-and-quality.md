# Architecture And Quality

Apply the ecosystem's official naming, package layout, formatting, typing and
import conventions. Organize by feature/domain and separate shared concerns
only where useful. Keep dependency direction clear; entry points should not own
business rules. Use interfaces, factories, patterns, and reusable components to
solve actual coupling or testability problems, not as speculative scaffolding.
Enforce important dependency boundaries with existing tooling where practical.

Keep current architecture, setup, operational commands, and test guidance in
canonical documents. Historical plans and decision records must not be treated
as current behavior. Update relevant docs when implementation or test changes
alter behavior, coverage scope, test commands, setup, or operational guidance.
Test-only changes also require a documentation update; when no useful doc change
applies, use a documented, reasoned bypass instead of adding noise. Record
decisions and trade-offs in Markdown; keep API comments concise and explain only
contracts or non-obvious invariants.

## Reusable Developer Tools

Give each repository a small set of reusable tools for its recurring local
development, test, CI, and release tasks, using the ecosystem's natural task
runner or scripts directory. Keep one canonical index with each tool's purpose,
prerequisites and exact invocation. During implementation, actively identify
repeated or failure-prone manual steps that can be made deterministic; automate
them when doing so materially improves repeatability or reduces toil. Test
scripts, avoid duplicate wrappers and one-off abstractions, and do not add
placeholder tools without a real recurring use.

Maintain known issues in the project's existing issue tracker or one canonical
document; link to it from contributor documentation instead of duplicating a
ledger. Record each issue's impact, severity, status, owner, workaround when
available, and next review or follow-up. Update or close entries as fixes land.
Keep sensitive details in an appropriately private location.

## Risk-Based Tests

Pick the lowest-cost layers that demonstrate the behavior and its risks:

- Unit: rules, parsing, validation, boundaries, and failure cases.
- Component/UI where applicable: interaction, accessibility, localization,
  responsive layouts, empty/loading/error states, and platform behavior.
- Integration: important workflows across real app boundaries, using fakes for
  external services and injectable time by default.
- Contract: schemas and third-party compatibility, separate from offline tests.
- Security/data integrity: authentication, authorization, migrations,
  concurrent edits, backup/restore, and failure recovery as relevant.
- Performance: representative workloads, reproducible baselines, measurable
  budgets, and physical-device evidence when hardware affects the result.

Test user-visible regressions at the lowest appropriate layer, adding broader
coverage when behavior crosses boundaries. Exercise data-loss paths: Undo,
retries, sync and restores must not overwrite later changes. Keep tests
isolated, deterministic, fast, and individually runnable; remove redundant
tests only when equivalent coverage is demonstrable. Coverage measures a
selection, not correctness; report its denominator and exclusions instead of
gaming a percentage. Record intentionally untested risks and ownership.
