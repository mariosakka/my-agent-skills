# DDD Module Conventions — colete-online server

The north star for `src/modules/**`. The `/ddd-review` skill and the CI lint
rules both derive from this file. It is **opinionated**: where existing modules
disagree, this picks one winner. Reference module: **`feature_request`** (cleanest
end-to-end). Scaling reference: **`payment_reconciliation`** (rich domain) — but
note it currently *violates* the boundary rules below; it is a cautionary example,
not a template.

> Severity legend: **[ERROR]** = blocks (lint-enforced where mechanical) ·
> **[WARN]** = should fix / migrate · **[INFO]** = guidance.

---

## 0. Decisions log (the divergences this resolves)

Each line is a fork the codebase currently disagrees on. **Veto any you dislike.**

| # | Topic | Winner | Loser(s) seen in tree |
|---|-------|--------|-----------------------|
| D1 | App orchestration unit | `application/use_cases/` + `*.use_case.ts` | `application/services/*Service` (account_transaction, financials, user) |
| D2 | Value object suffix | `*.value_object.ts` *(soft naming convention — not gated)* | `*.vo.ts` (authority_search, feature_request, shipping_point_widget) |
| D3 | Non-persistence outbound iface | `application/ports/*.port.ts` **when the application needs it**; a port the **domain** needs lives in `domain/ports/*.port.ts` (see §2) | `application/interfaces/` |
| D4 | Persistence iface | `domain/repository_interfaces/*.repository.interface.ts` | — (already universal) |
| D5 | Public surface | thin, **curated** `index.ts` barrel — never `export *` | absent in 6/10 modules |
| D6 | Cross-module calls | only via `shared/contracts/**` + `*.contract.adapter.ts`, or another module's `index.ts` | deep imports into another module's domain/app/infra |
| D7 | DI tokens | per-module `tokens.ts` (`as const`), no bare string literals | bare `"IFooRepository"` duplicated at every site |
| D8 | DI framework in domain | domain is framework-free — **no `tsyringe`** in `domain/**` | `@injectable` domain services in payments |
| D9 | Error handling | `neverthrow` `Result`/`ResultAsync` in domain + application | thrown exceptions in domain/app |
| D10 | ~~Domain error files~~ | **dropped** — one-error-per-file is file-granularity taste with no correctness payoff; either layout is fine | — |
| D11 | Entity construction | private ctor + static `create()`/`fromPrimitives()`, guarded | public-ctor + getters (payment_method) |

Neverthrow stays allowed in `domain/**` (it's a pure FP result type, not a
framework). tsyringe does not (D8).

### Revisions (2026-06, post multi-lens review)

A review of these rules against DDD canon, clean/hexagonal, pragmatic
cost/benefit, TS-idioms, testability, FP/type-driven, and an adversarial pass
produced four adjustments — all reflected above and in the rule sections:

- **B3 pure-util allowlist.** B3's value is keeping *effects, IO and framework
  coupling* out of the domain — not banning pure functions. A side-effect-free
  total function (e.g. `diffDays`) imported via an alias compromises nothing.
  The domain may import an **audited pure-utility** module on the allowlist
  (`DOMAIN_PURE_UTIL_ALLOWLIST` in `ddd-lint`); the blanket alias ban over-fires
  otherwise. Keep the list tight and re-audit before adding (the module must have
  no imports and no side effects).
- **D3 ports owned by the requirer.** D3 and D4 must use the *same* principle:
  a port lives in the layer that **declares the need**. Persistence ports →
  domain (D4); non-persistence ports → application **only when the application
  needs them**, and **domain** when a domain service needs them (`domain/ports/`).
  Placing a domain-needed port in application forces a B1 violation.
- **D5 thin curated barrel.** Mandatory barrels are a TS hazard (cycles, build
  perf, tree-shaking). Keep the barrel but make it thin and hand-curated — the
  public routes/jobs/types + the di.config side-effect — never `export *`.
- **D10 dropped.** One-error-per-file is filing ceremony with no correctness
  payoff.

---

## 1. Layers & dependency direction

Every module is exactly three layers:

```
src/modules/<module>/
  index.ts          # thin, curated public barrel (no `export *`) — the ONLY cross-module entry point (D5)
  tokens.ts         # DI string tokens as `as const` (D7)
  di.config.ts      # tsyringe composition root (side-effect on import)
  domain/
  application/
  infrastructure/
```

**Allowed import direction (strict):** `infrastructure → application → domain`.

- **[ERROR] B1** `domain/**` must not import `application/**` or `infrastructure/**`.
- **[ERROR] B2** `application/**` must not import `infrastructure/**`.
- **[ERROR] B2a** `application/**` must not import a Prisma-client alias
  (`@prisma-client/*`) — persistence belongs in `infrastructure/**`, reached
  through a repository interface declared in `domain/`. Importing the ORM client
  directly into a use-case leaks persistence into the application layer.
- **[ERROR] B3** `domain/**` must not import any tsconfig path alias
  (`@server/*`, `@order/*`, `@prisma-client/*`, `@helper/*`, …) — it stays pure.
  A repository *interface* describes persistence in domain terms; it must not
  reference `@prisma-client/*` types (seen in payment_reconciliation).
  **Exception:** an *audited* pure, side-effect-free utility module on the
  `DOMAIN_PURE_UTIL_ALLOWLIST` (e.g. `@helper/date/date_utils`) may be imported —
  the rule targets effects/IO/framework coupling, not pure total functions. The
  module must have zero imports and no side effects; keep the list tight.
- **[WARN] B8** `application/**` and `domain/**` importing legacy `@server/*`
  (the old `src/services` tree) is tech-debt; allowed only transitionally and
  must be reported.
- **[INFO]** `@logger` / `@config` are allowed everywhere *except* `domain/**`.

## 2. Cross-module boundaries

- **[ERROR] B6** A module may import another module **only** at
  `src/modules/<other>/index` (its barrel) or `src/modules/shared/contracts/**`.
  Reaching into `<other>/domain|application|infrastructure/**` is leakage.
- Inter-module behavior goes through a **contract**: declare
  `shared/contracts/<provider>/<x>.contract.ts` (interface only); the provider
  implements it as `<provider>/infrastructure/adapters/<x>.contract.adapter.ts`
  and registers it in its `di.config.ts`. Consumers `@inject` the contract token.
- **[WARN]** Legacy code (`src/routes`, `src/services`, …) importing a module is
  allowed **only** at `index.ts` or `infrastructure/controllers/**` (route
  wiring). Legacy reaching into a module's `domain/**` is leakage to report.

**Port ownership (D3/D4 — one principle).** A port lives in the layer that
**declares the need**, never by technology category. Persistence ports →
`domain/repository_interfaces/` (D4). A non-persistence outbound port →
`application/ports/` when a use-case needs it, or `domain/ports/` when a
*domain* service needs it (D3). Putting a domain-needed port in `application/`
forces the domain to import application (a B1 violation), so let the requirer
own it.

## 3. Domain layer (`domain/`)

Pure business model. No framework, no I/O, no aliases except audited
pure-util allowlist entries (§1, B3).

| Concern | Folder | File suffix | Notes |
|---------|--------|-------------|-------|
| Entities / aggregates | `entities/` | `*.entity.ts` | private ctor + static `create`/`fromPrimitives`, guarded (D11) |
| Value objects | `value_objects/` | `*.value_object.ts` | private ctor + static factory; immutable (D2) |
| Enums | `enums/` | `*.enum.ts` | `as const` object + extracted type — **never `enum`** (repo rule) |
| Domain errors | `errors/` | `*.error.ts` | extend a shared base error (one-per-file no longer required, D10 dropped) |
| Repository interfaces | `repository_interfaces/` | `*.repository.interface.ts` | return `ResultAsync<…, PersistenceError>` (D4) |
| Outbound ports (domain-needed) | `ports/` | `*.port.ts` | a non-persistence outbound port a **domain** service needs; impl'd by an infra adapter, bound by token (D3) |
| Pure domain services | `services/` | `*.service.ts` | stateless, **no `@injectable`** (D8); only if logic spans entities |

## 4. Application layer (`application/`)

Orchestration + boundaries. `@injectable`, depends on domain + ports only.

| Concern | Folder | File suffix | Notes |
|---------|--------|-------------|-------|
| Use cases | `use_cases/` | `*.use_case.ts` | one public `execute()`-style method; orchestration only (D1) |
| DTOs | `dto/` | `*.dto.ts` | shapes crossing the app boundary; see §6 re: OpenAPI |
| Mappers | `mappers/` | `*.mapper.ts` | domain ↔ DTO |
| Outbound ports | `ports/` | `*.port.ts` | non-persistence outbound (notifier, queue, email) (D3) |
| Input schemas | `schemas/` | `*.schema.json` | AJV validation **and** OpenAPI source (§6) |

- **[WARN]** `application/services/*Service` as the *entry point* (no use case)
  is the pre-D1 pattern — flag and suggest a use case. Genuinely shared internal
  application helpers may stay as services.

## 5. Infrastructure layer (`infrastructure/`)

Adapters to the outside world. The only layer that may touch Prisma, HTTP,
queues, aliases.

| Concern | Folder | File suffix |
|---------|--------|-------------|
| Repository impls | `repositories/` | `*.prisma.repository.ts` (+ `*_row.mapper.ts`) |
| Contract adapters | `adapters/` | `*.contract.adapter.ts` (impl a `shared/contracts` iface) |
| Other adapters | `adapters/` | `*.adapter.ts` (impl an `application/ports` port) |
| Controllers | `controllers/` | `*.controller.ts` + sibling `*.types.ts` (§6) |
| Error mappers | `error_mapper/` | `*_error_mapper.ts` (registered under `IApiErrorMapper`) |
| Queue/event listeners | `listeners/` | `*.listener.ts` |
| Unit of work | `unit_of_work/` | `*.uow.ts` |

## 6. Types & OpenAPI (D — both severities)

- The API boundary is the OpenAPI spec at
  `shared/apis/public/coleteonline_web/openapi.json`, which composes the module
  `application/schemas/**/*.schema.json` via `$ref`. Those schemas are
  **single-sourced**: same file feeds AJV (runtime) and openapi-typescript
  (compile-time, → `shared/apis/generated/coleteonline_web.generated.types.ts`).
- **[ERROR] T1** Do not hand-redeclare a shape that already exists as a generated
  schema. (Seen: `payments/application/dto/payment_methods.response.dto.ts`
  duplicates `payment_methods.response.schema`.) Derive from the generated types
  instead.
- Controllers extract from generated types in a sibling `*.types.ts`:
  `type Route = paths["/path"]; export type XResponseType = Route["get"]["responses"]["200"]["content"]["application/json"]`.
- **[WARN] T2** A controller request/response (or an Angular HTTP call) that does
  **not** flow through the generated OpenAPI types at the boundary — migrate it.
- After editing any `openapi.json` / `*.schema.json`, regenerate:
  `npx openapi-typescript src/modules/shared/apis/public/coleteonline_web/openapi.json -o src/modules/shared/apis/generated/coleteonline_web.generated.types.ts`.
  **[WARN] T3** generated file out of sync with the spec.

## 7. tsyringe / DI

- One global `container`. Each module owns `di.config.ts` (composition root) that
  runs `container.register(...)` on import.
- **[ERROR] DI1** Every string token used in `@inject`/`@injectAll` must be
  registered in some loaded `di.config.ts`. (Unregistered/typo'd tokens only fail
  at resolve time today — this lifts it to a build check.)
- **[WARN] DI2** Tokens should come from a per-module `tokens.ts` `as const`, not
  bare duplicated string literals (D7).
- **[ERROR] DI3** Interfaces/ports/contracts bind by **string token**
  (`register("IFooRepository", { useClass: … })`); concrete use-cases/controllers
  self-bind by class ref.
- **[ERROR] DI4 — registration reachability.** For each server entry point
  (`server.ts`, `admin_dashboard_server.ts`, `jobs_server.ts`, …), every module
  whose controllers/handlers are mounted by that process must have its
  `di.config` imported (directly or via `index.ts`) **before** routes resolve,
  and `./config/module_aliases` (→ `reflect-metadata`) must be the first import.
  This is the most fragile invariant in the codebase.
- **[INFO]** `@injectAll("IApiErrorMapper")` collects *all* modules' mappers on
  the shared container — expected, not a bug.

## 8. Errors (neverthrow)

- **[ERROR] E1** Domain + application return `Result`/`ResultAsync`; no `throw`
  for expected failures (D9). Infra adapters may catch thrown lib/ORM errors at
  the edge and map them into a `Result`.
- Controllers convert `Result` → HTTP via an injected `IApiErrorMapper`; domain
  errors map to RFC-7807 problem types (`components["schemas"]["problem.*"]`).

## 9. Naming & tests

- **[ERROR] N1** Files `snake_case`; classes/types `PascalCase`.
- **[INFO]** Tests colocated as `*.test.ts` next to the unit. Domain + use cases
  should be unit-tested (feature_request is the model).
