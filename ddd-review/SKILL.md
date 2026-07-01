---
name: ddd-review
description: Review a colete-online server DDD module (src/modules/**) for compliance with the team conventions — layer/import-boundary leakage, tsyringe wiring, OpenAPI type usage & duplication, and DDD building-block quality. Use when the user says "/ddd-review", "review this module", "is this module DDD-correct", "check DDD compliance", "check the layering / import boundaries", "did I wire tsyringe right", "review my DDD implementation", or opens/edits code under server/src/modules and wants it checked against the conventions. Diff-by-default (reviews changed files), full-module audit when a module is named. Server-side only — the Angular client has a separate companion review.
---

# ddd-review — is this module DDD-correct?

You are checking a server module under `server/src/modules/**` against the team's
DDD conventions. The **source of truth is `CONVENTIONS.md`** in this skill's
directory — read it first, every run; it defines the layers, naming, the rule IDs
(B1, B2, B2a, B3, B6, B8, D8, DI1–DI4, T1–T3, E1, N1), and the decisions log
(D1–D11).
Cite rule IDs in findings so they're traceable.

The job is **merge-readiness against the conventions**, not general code review.
Don't drift into taste/perf/style — those belong to `/code-review`. Mention a
quality issue only if it bears on a convention.

This skill **advises**; it does not edit files unless the user explicitly asks
("fix them"). Default output is a report.

## Two halves: mechanical (script) + judgment (you)

The deterministic checks live in `server/scripts/ddd-lint/` and are the ground
truth for the import-graph and DI-token rules — **run them, don't re-derive them
by eye** (eyeballing import direction across relative paths is exactly where
manual review fails). Then you add the judgment-level review the script can't do.

## 1. Determine scope

- **A module is named** ("/ddd-review payments", "review the payments module") →
  full-module audit.
- **Otherwise** → diff mode: the changed files on this branch. Compute them:
  ```bash
  git -C server diff --name-only origin/development...HEAD -- 'src/modules/**/*.ts'
  git -C server diff --name-only -- 'src/modules/**/*.ts'   # + uncommitted
  ```
  Union them, drop `*.test.ts`/`*.d.ts`. If none are under `src/modules/`, say so
  and stop (nothing DDD to review).

## 2. Run the mechanical checks

From `server/`:
```bash
npm run ddd:lint -- --json --module <name>          # full audit
# or, diff mode:
npm run ddd:lint -- --json --files <comma-separated changed files>
```
Parse the JSON: `newErrors`, `warnings`, `baselinedRemaining`, `fixed`. In diff
mode, `newErrors` are violations **this branch introduced** — these are the ones
that matter most. Baselined errors are pre-existing debt (report only if the file
under review is one of them). Treat the script output as fact for B1/B2/B2a/B3/
B6/B8/D8/DI1; spot-check one or two against the code so a parser edge case never
silently drives the verdict.

## 3. Judgment review (what the script can't do)

For each changed file / each layer of the named module, read the code and check:

**Type duplication & OpenAPI (T1/T2/T3 — the script only name-matches).**
- T1 [error]: a hand-written `interface`/`type` whose *shape* already exists as an
  OpenAPI-generated schema (`shared/apis/generated/coleteonline_web.generated.types.ts`,
  keyed `components["schemas"]["<id>.schema"]`). The known offender pattern is in
  `payments/application/dto/*` — verify structurally, not just by name.
- T2 [warn]: a controller request/response (or, later, an Angular HTTP call) that
  does **not** flow through the generated OpenAPI types at the boundary. Controllers
  should extract from `paths[...]` in a sibling `*.types.ts`.
- T3 [warn]: `*.schema.json` changed but the generated types weren't regenerated
  (the file is single-sourced for AJV + openapi-typescript). Regen command is in
  `CONVENTIONS.md` §6.

**DDD building blocks (D8–D11, E1).**
- Entities: private ctor + static `create()`/`fromPrimitives()`, guarded; behavior
  returns `Result` (D11). Value objects: private ctor + factory, immutable, no
  identity. Flag anaemic public-ctor+getter "entities".
- Domain & application return `neverthrow` `Result`/`ResultAsync`; no `throw` for
  expected failures (E1, D9). Infra adapters may catch and map to `Result`.
- Use cases (D1): one orchestration entry point, depend on domain + ports only, no
  business rules that belong in the domain. An `application/services/*Service`
  used as the entry point is the pre-D1 pattern → flag [warn] to migrate.

**Cross-module & contracts (B6).**
- The script flags deep cross-module imports. You additionally verify the *seam*:
  inter-module calls go through a `shared/contracts/<provider>/*.contract.ts`
  interface implemented by `<provider>/infrastructure/adapters/*.contract.adapter.ts`
  and injected by token — not by importing the other module's `index` and reaching
  for internals through it.

**tsyringe wiring (DI2, DI3, DI4 — the script only does DI1).**
- DI3: interfaces/ports/contracts bind by string token (`register("IFoo", {useClass})`);
  concrete use-cases/controllers self-bind by class ref.
- DI2 [warn]: tokens should come from a per-module `tokens.ts` `as const`, not bare
  duplicated string literals.
- **DI4 [error] — registration reachability (the high-value manual check).** For
  every server entry point that mounts this module's controllers/handlers
  (`server.ts`, `admin_dashboard_server.ts`, `jobs_server.ts`,
  `mails_processor_server.ts`, `mobile_app_server.ts`, `queue_*_server.ts`,
  `widget_server.ts`), confirm that entry point imports the module's `di.config`
  (directly or via its `index.ts`) **and** imports `./config/module_aliases`
  (→ `reflect-metadata`) first. A controller mounted in a process whose
  `di.config` isn't loaded throws only at request time — grep for where the
  module's controllers/routes are mounted, then confirm the matching di.config
  import exists in that entry file.

**Structure & naming (N1, D2–D5).**
- Folders/suffixes per `CONVENTIONS.md` §3–§5 (`*.use_case.ts`, `*.value_object.ts`,
  `*.repository.interface.ts` in `domain/repository_interfaces/`, `*.port.ts` in
  `application/ports/` **or** `domain/ports/` per the requirer (D3),
  `*.prisma.repository.ts`, etc.). snake_case files, PascalCase types. A thin,
  curated `index.ts` barrel — never `export *` (D5).
- No TS `enum` — `as const` objects only (repo-wide rule).
- D10 (one-error-per-file) was dropped — don't flag aggregate `*.errors.ts`.

## 4. Output

Lead with a one-line verdict, then findings grouped by severity, each as:

```
[<RULE>] <severity>  <file>:<line>
  <what> — <why it violates the convention>
  Fix: <concrete change>
```

Order: new errors (diff mode) / all errors (audit) → warnings → notes. Separate
"introduced by this change" from "pre-existing (baselined)" so the author knows
what's theirs. End with the scannable block:

```
## <🟢|🟡|🔴> DDD Review — <module or "diff">

| | |
|---|---|
| **Verdict**  | 🟢 Conforms · 🟡 Conforms w/ warnings · 🔴 Violations to fix |
| **Scope**    | <module name> / <N changed files> |
| **Errors**   | <N new> new · <N> pre-existing (baselined) |
| **Warnings** | <N> (B8 legacy reach, T2 OpenAPI, DI2 tokens, …) |
| **Boundaries** | <ok / list B1/B2/B2a/B3/B6 hits> |
| **tsyringe** | <DI1 ok? DI4 reachability ok? tokens.ts?> |
| **Types**    | <T1 duplication? T2 OpenAPI at boundary?> |
| **Building blocks** | <entities/VOs/use-cases/neverthrow notes> |
| **To merge** | <the concrete must-fix list, or "nothing"> |
```

Verdict: 🔴 if any **new** error (diff) or any error (audit). 🟡 if only warnings
or only pre-existing/baselined errors touch the reviewed files. 🟢 if clean.

Then offer next steps (don't do them unprompted): fix the findings, regenerate the
OpenAPI types, or run `npm run ddd:lint:baseline` if a baselined issue was fixed.

## Notes
- If `git`/`npm` aren't usable in the cwd, `cd server` first; the script needs no
  DB or services.
- The Angular client checks (client consuming shared/OpenAPI types) are a separate
  companion skill — if asked about the client, say it's out of scope here.
