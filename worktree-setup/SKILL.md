---
name: worktree-setup
description: >-
  Create a ready-to-run git worktree for the colete-online platform monorepo —
  both when explicitly asked AND as the default way to START a quick, isolated
  change without disturbing the current branch. Use when the user says "make a
  worktree for X", "check out PR #N in a worktree", "spin up a worktree", BUT
  ALSO when they want to begin a fresh fix in isolation: "let me quickly fix Y",
  "quick patch for Z", "start a new fix", "try this on a separate branch", "work
  on this without touching what I've got open". A bare `git worktree add` is NOT
  enough in this repo — node_modules, env files, and a couple of gitignored
  generated files are per-worktree and must be set up, or every npm/prisma/tsx
  command fails with confusing errors. Skip when the user is mid-change on the
  current branch and just wants to edit in place.
---

# worktree-setup — a worktree that actually runs

## Why this exists

`git worktree add` gives you the *tracked* files only. In this monorepo three
categories of per-worktree state are **gitignored and therefore absent** in a
new worktree, and each produces a confusing failure if you skip it:

- **`node_modules/`** — absent → `Cannot find module 'dotenv'` (or `prisma`,
  `tsx`, …) the moment any script or Prisma config loads. Looks like a code bug;
  it's a missing install.
- **env files (`.env.development`, etc.)** — absent → `environment.ts` `exit(1)`s
  with "Failed to load env file" on *any* server/Prisma command, because the
  Prisma config (`prisma-*.config.ts`) imports `src/config/environment`.
- **generated config (`src/config/urls.ts`, `src/config/rabbitmq_constants.ts`)**
  — gitignored, written during build/setup → absent → import errors at **build**
  time too (`src/config/constants.ts` imports `./rabbitmq_constants`, so `tsc`
  fails with `Cannot find module './rabbitmq_constants'`), not only when the
  server boots.

Set these up explicitly and the worktree behaves like your main checkout.

## Conventions used below

- **`$MAIN`** = your main, long-lived platform checkout — the one you keep on
  `development`. It's the source of truth for the gitignored files you'll copy.
  Set it once: `MAIN=$(git rev-parse --show-toplevel)` from that checkout, or
  point it at wherever yours lives.
- Worktrees are created as **siblings** of `$MAIN` (e.g. `$MAIN/../platform-<name>`),
  so they don't nest inside it.

## Quick start (the common case)

Start an isolated branch to fix something, with just-enough setup — run from
your `$MAIN` checkout:

```bash
MAIN=$(git rev-parse --show-toplevel)
NAME=COL-XXX-slug
WT="$MAIN/../platform-$NAME"

git worktree add -b feature/$NAME "$WT" origin/development
cp "$MAIN/server/.env.development" "$WT/server/.env.development"
cp "$MAIN"/server/src/config/{urls.ts,rabbitmq_constants.ts} "$WT"/server/src/config/
cd "$WT/server" && npm ci --legacy-peer-deps   # the only slow step (minutes)
```

That's a buildable server worktree. `npm ci` is the only slow part; skip it only
if you're just reading code (anything that runs `prisma`/`tsx`/a build needs the
install — see the per-task table). To type-check your fix before pushing, see
step 5. The numbered steps below are the same commands with full rationale.

## Steps

### 1. Create the worktree

For an existing branch (e.g. reviewing/working a PR):

```bash
git fetch origin <branch> --quiet
git worktree add "$MAIN/../platform-<name>" <branch>
```

For new work, base on `development` (repo convention — never `main`), and embed
the Jira key in the branch name:

```bash
git worktree add -b feature/COL-XXX-slug \
  "$MAIN/../platform-<name>" origin/development
```

This never touches other worktrees' uncommitted work — that's the whole point of
using one. When done, `git worktree remove <path>` (it refuses if there are
uncommitted changes, which is a feature).

### 2. Install dependencies (per project you'll touch)

node_modules is per-worktree. Use the **same command CI uses** so installs are
deterministic:

```bash
cd <worktree>/server && npm ci --legacy-peer-deps
```

Do the same in `client/`, `client-admin/`, or `cbox-web/` only if you'll build/run
them. This is the slow step (minutes) — expect it.

### 3. Copy the env file — `.env.development`, **never `.env`**

```bash
cp "$MAIN/server/.env.development" <worktree>/server/.env.development
```

**Critically: copy `.env.development`, not `.env`.** Per `environment.ts`, the
`production` environment (and any unset `NODE_ENV`, which defaults to production)
loads **`.env`** — that is the *production* env file. You almost never want a
worktree running with production config/credentials. Local dev uses
`.env.development` (via `serve:dev` → `NODE_ENV=development`) or `.env.local`
(via the local-DB workflow). So copy the dev template; leave `.env` out.

### 4. Copy the gitignored generated config (needed to BUILD or run — not for prisma alone)

`src/config/constants.ts` imports `./rabbitmq_constants`, so **`npm run
only-build` (tsc) fails without these** — not just running the server.
`prisma migrate` / `prisma-generate` do *not* need them:

```bash
cp "$MAIN/server/src/config/urls.ts"               <worktree>/server/src/config/urls.ts
cp "$MAIN/server/src/config/rabbitmq_constants.ts" <worktree>/server/src/config/rabbitmq_constants.ts
```

Alternatively regenerate them in-place (`scripts/setup-rabbitmq.sh` writes
`rabbitmq_constants.ts`; `urls.ts` is produced during build). Copying from your
known-good main checkout is faster and avoids surprises.

### 5. Build / type-check before you push

`npm run only-build` = `tsc --build` + eslint + asset copy — the same check CI's
`Build Server` runs. Two non-obvious requirements beyond steps 2–4:

```bash
cd <worktree>/server
NODE_ENV=development npm run prisma-generate                   # (a)
NODE_OPTIONS=--max-old-space-size=8192 npm run only-build      # (b)
```

- **(a)** `prisma-generate` executes the Prisma config (which loads
  `environment`), so it needs `NODE_ENV` set — unset defaults to production and
  dies with `ENOENT … '.env'`. Until it runs, `@prisma-client/cbox` /
  `@prisma-client/delivery` don't exist and you get a *cascade* of
  `Cannot find module '@prisma-client/*'` + implicit-`any` errors that vanish
  once generated. Generate first.
- **(b)** `tsc --build` over this project blows the default ~4 GB V8 heap
  (`FATAL ERROR: Reached heap limit`); `--max-old-space-size=8192` fixes it.

Colocated `*.test.ts` (vitest) don't run in CI — run them explicitly with
`NODE_ENV=development npx vitest run <file>` when correctness leans on them.

## What each task actually needs

Don't over-provision — match the setup to the goal:

| Goal | needs |
|---|---|
| read/inspect code, get a PR's file SHAs | nothing (bare worktree is fine) |
| `prisma migrate` / generate SQL | deps (2) + `.env.development` (3); **not** the generated config (4) |
| build / type-check (`npm run only-build`) | deps (2) + `.env.development` (3) + generated config (4) + the prisma-generate & heap bump (5) |
| **run** a server process | all of (2)(3)(4), plus a local DB / `.env.local` |

## Running a local DB in the worktree (when needed)

Use `scripts/local.sh` — but there's an ordering trap: `environment.ts` exits if
its env file is missing, and `cmd_start` runs the DB/`migrate deploy` step
**before** it generates `.env.local`. So generate `.env.local` first, and always
pass `NODE_ENV=local`:

```bash
cd <worktree>/server
./scripts/local-env.sh --instance=<N> --schema=delivery     # writes .env.local first
NODE_ENV=local ./scripts/local-db.sh start --instance=<N> --schema=delivery
```

Pick a free instance (`docker ps | grep col-local-mysql`); ports are
`3306+N` (delivery) / `3406+N` (cbox). The Percona image does an init-then-restart
on first boot, so a create-DB/migrate step right after "ready" can hit a brief
socket error — just re-run it once the container is fully up. Note: under
`NODE_ENV=local`, logs are JSON unless `LOG_PRETTY=1` is set in `.env.local`
(COL-537).

## Cleanup

```bash
git worktree remove <worktree>     # refuses if there are uncommitted changes
```

If you generated a local DB, stop it first: `NODE_ENV=local ./scripts/local.sh
stop --instance=<N>` (or `local-db.sh stop`).
