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

## Localization And User-Facing Text

For user-facing applications, keep visible text in the framework's canonical
localization catalogs and use generated or typed accessors where supported. Do
not scatter UI strings through widgets, views, error handlers, or notifications.
Build variable messages with named catalog parameters, plural/select rules, and
locale-aware date, number, and currency formatters; do not concatenate fragments
or format values with locale-insensitive defaults. Keep stable identifiers,
protocol values, logs, and developer-only diagnostics separate from translated
copy. Record localization as not applicable only when the product has no
user-facing text or the requested scope explicitly excludes it.

Test catalog parsing/generation, key and placeholder parity across supported
locales, fallback behavior, parameter substitution, plural forms, and locale-
sensitive formatting. Add a technology-specific lint or static check for
unlocalized visible strings where the ecosystem supports one; review its known
false positives and narrow exceptions. Include accessibility labels and
validation/error messages in the localization boundary. Avoid constructing text
from separately translated fragments because grammar and word order vary by
locale.

## Reusable Developer Tools

Automate repeated or failure-prone development, test, CI, and release tasks
when doing so materially improves repeatability or reduces toil. Use the
ecosystem's task runner, test scripts, and one canonical developer-tool index;
avoid duplicate wrappers and placeholder tools. See
[indexes and inventories](indexes-and-inventories.md) for tool, test, feature, contract, decision,
workflow, issue, and optimization catalogs, including reciprocal test-index
drift checks.

Maintain known issues in the project's existing issue tracker or one canonical
document; link to it from contributor documentation instead of duplicating a
ledger. Record each issue's impact, severity, status, owner, workaround when
available, and next review or follow-up. Update or close entries as fixes land.
Keep sensitive details in an appropriately private location.

## Network, Cache, And Performance Efficiency

- Inventory network and expensive I/O origins before optimizing. Measure
  representative request counts, payload sizes, latency, cache hit/miss rates,
  and relevant startup or interaction timings; do not optimize from intuition
  alone.
- Reduce avoidable traffic at shared boundaries: request only needed fields,
  batch related lookups, avoid per-item/N+1 fetches, deduplicate identical
  in-flight work, debounce noisy user input when it preserves UX, and bundle
  related data when that is cheaper than repeated round trips. Respect provider
  limits and pagination rather than fetching unbounded datasets.
- Define a cache policy per data type: identity/key, freshness/TTL, invalidation,
  schema/version behavior, stale/offline fallback, and privacy. Use provider
  validators such as ETag when available. Do not cache credentials or private
  data in shared locations, and do not trade correctness for a higher hit rate.
- Bundle immutable, small, frequently needed assets/data only when measurements
  justify the startup/offline benefit; account for binary size, update cadence,
  licensing, and stale bundled content. Cache or decode large media at display-
  appropriate sizes instead of repeatedly transferring or decoding originals.
- Set request and performance budgets for critical user flows. Protect them
  with deterministic fake-transport tests and focused regression checks; use
  physical-device profiling when device hardware or rendering is material.
- Keep a maintained request/performance ledger in the repository's canonical
  engineering or performance docs. For each optimization, record the baseline,
  change, measured savings, correctness/freshness trade-off, evidence commit or
  run, and a recheck trigger. Update or retire entries when behavior changes;
  do not turn one-time measurements into permanent claims without provenance.
  Maintain one index of optimization candidates and outcomes, linking each item
  to its evidence and the canonical ledger rather than duplicating measurements.
- For device-sensitive products, benchmark a current reference device and an
  older or lowest-supported device with the same scenario and build mode. Record
  device model/tier, OS, app commit/build, benchmark scenario, run count, metric
  definitions and results, and relevant conditions such as thermal state. Keep
  results with the performance ledger or as CI artifacts linked from it so
  regressions and trade-offs across device tiers remain visible. Use emulators
  for repeatable screening, but confirm hardware-dependent conclusions on
  representative physical devices.

## Risk-Based Tests

Every feature or behavior-change plan must assess each layer below, plus any
domain-specific layers. Record the planned test or a reasoned N/A for every
layer; do not silently omit a category. Implement and run tests for applicable
risks before merge, or record the blocked check and owner. Adding behavior adds
tests; changing behavior updates the relevant tests; removing behavior removes
or rewrites tests that describe the removed behavior. Keep tests aligned with
the current product, not as historical leftovers.

Pick the lowest-cost layers that demonstrate the behavior and its risks:

- Drift/contract: schemas, generated artifacts, manifests, persistence formats,
  API contracts, and compatibility between duplicated sources of truth.
- Unit: rules, parsing, validation, boundaries, and failure cases.
- Integration: important workflows across real app boundaries, using fakes for
  external services and injectable time by default.
- Component/UI where applicable: interaction, accessibility, localization,
  responsive layouts, empty/loading/error states, and platform behavior.
- End-to-end/smoke: critical user journeys and installation/startup paths.
- Security/data integrity: authentication, authorization, migrations,
  concurrent edits, backup/restore, and failure recovery as relevant.
- Performance: representative workloads, reproducible baselines, measurable
  budgets, network/request counts where applicable, and physical-device
  evidence when hardware affects the result.
- Other domain-specific checks: for example accessibility, concurrency,
  localization, offline behavior, or migration verification where relevant.

Test user-visible regressions at the lowest appropriate layer, adding broader
coverage when behavior crosses boundaries. Exercise data-loss paths: Undo,
retries, sync and restores must not overwrite later changes. Keep tests
isolated, deterministic, fast, and individually runnable; remove redundant
tests only when equivalent coverage is demonstrable. CI and local change checks
must require test changes alongside source additions, edits, and removals;
intentional exceptions need a documented `Tests-Not-Required: <reason>`.
Coverage measures a selection, not correctness; report its denominator and
exclusions instead of gaming a percentage. Record intentionally untested risks
and ownership.
