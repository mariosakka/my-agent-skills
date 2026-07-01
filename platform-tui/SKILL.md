---
name: platform-tui
description: Use when working with the platform repo's .scenarios/ CLI — running instance/scenario/process commands, or modifying the bash scripts in .scenarios/.
---

# Platform CLI Reference

Entry point: `bash ./platform.sh <command>` at repo root. Default (no args) = TUI.

## First-run setup

A fresh clone needs these steps in order before the stack works:

```bash
# 0. Check for port conflicts — old containers (e.g. col-local-mysql-1-delivery
#    on 3307, col-local-redis-1 on 6380) will cause "port already allocated"
#    errors on `up`. Stop any that overlap with the platform port blocks first:
docker ps --format "{{.Names}}\t{{.Ports}}"
# Stop conflicting ones: docker stop <name>

# 1. Env files — TWO separate files are required (different consumers/formats):
#
#   .env.local          (repo root) — consumed by platform.sh → docker run --env-file
#                        strict KEY=VALUE (no comments, no trailing spaces)
#                        holds MYSQL_ROOT_PASSWORD, REDIS_PASSWORD, etc.
#
#   server/.env.local   (server dir) — consumed by Node via dotenv as a fallback.
#                        Inside a platform container all vars already arrive via
#                        --env-file, so this file is NOT required when running
#                        through platform.sh. Only needed for bare `npm run
#                        start:dev` outside Docker.
cp .env.local.example .env.local
# server/.env.local is optional when using platform.sh — skip if running
# through Docker only.

# 2. Bring the scenario up — this is now a single command that does everything:
#    - creates missing containers (auto-builds images if not present)
#    - starts containers + applies pm2
#    - waits for MySQL, then runs migrations on a fresh DB
#    - seeds the delivery DB if it hasn't been seeded yet
bash ./platform.sh up
```

After this, the client reaches `server.ts` on port 3001 and `/auth/login` works.

Use `--no-migrate` or `--no-seed` to skip those steps if needed.

### Status line (one-time setup per machine)

The active scenario name can be shown in the Claude Code status bar. This is wired into the global statusline script — check once if it's already set up:

```bash
grep -q 'ACTIVE_SCENARIO' ~/.claude/statusline-command.sh 2>/dev/null && echo "already set up" || echo "not set up"
```

If not set up, add the following block to `~/.claude/statusline-command.sh` just before the `# Output` comment at the bottom:

```bash
# Active scenario (platform repo only)
state_file="$cwd/.scenarios/state"
if [ -f "$state_file" ]; then
  scenario=$(grep -m1 '^ACTIVE_SCENARIO=' "$state_file" 2>/dev/null | cut -d= -f2)
  if [ -n "$scenario" ]; then
    scenario_part=$(printf '  \033[00;35mscenario: %s\033[00m' "$scenario")
    line2="${line2}${scenario_part}"
  fi
fi
```

This adds `scenario: <name>` in purple to the second status line, only when working in this repo.

### Claude Code permissions (do this first, before anything else)

`platform.sh` commands require per-command approval in Claude Code unless the allow-rules have been written to `.claude/settings.local.json`. Without them Claude will ask the user to approve — or run — every command manually instead of doing it itself.

**Always run this check as the very first action when the skill is invoked:**

```bash
grep -q 'platform\.sh' .claude/settings.local.json 2>/dev/null && echo "already allowed" || echo "not yet allowed"
```

If the output is `not yet allowed`, immediately run:

```bash
bash ./platform.sh setup --yes
```

This writes the allow-rules directly — no TTY or user interaction needed. Do **not** write the file manually; `setup --yes` handles the merge safely. After this runs once, all subsequent `platform.sh` commands in this session execute without per-command approval.

On the **first interactive run** (by the human in a real terminal), `platform.sh` also offers this automatically. `./platform.sh setup` (without `--yes`) re-triggers the interactive prompt.

## Two .env files

There are **two** env files with different consumers, formats, and both are required:

| File | Consumer | Format | Notes |
|------|----------|--------|-------|
| `./.env.<env>` (repo root) | `platform.sh` → `docker run --env-file` | strict `KEY=VALUE` | Docker rejects trailing whitespace / inline comments. Holds `MYSQL_ROOT_PASSWORD`, etc. |
| `server/.env.<env>` | Node server via `dotenv` (`config/environment.ts`) | lenient (comments/whitespace OK) | Optional when running through `platform.sh` — inside a platform container a missing file is silently ignored (info-logged) because vars already arrive via `--env-file`. Only required for bare `npm run start:dev` outside Docker. |

They can't be the same file (different format strictness + different consumers). A `server/.env.local.example` template ships in `server/`.

## Commands

```bash
# Instances
bash ./platform.sh instance list
bash ./platform.sh instance create --type=<type> --env=<env> [--num=<N>]
     [--node=<ver>] [--mysql-version=<ver>] [--sql-mode=<mode>]
bash ./platform.sh instance start|stop|restart|delete <name>
bash ./platform.sh instance pm2-status <name>          # server only
bash ./platform.sh instance env        <name> [--reveal]
bash ./platform.sh instance switch-env <name> --env=<env> --yes

# Scenarios
bash ./platform.sh scenario list|show|create|apply|delete <name>
bash ./platform.sh scenario set-description <name> <text>
bash ./platform.sh scenario add-infra|remove-infra <name> <container>
bash ./platform.sh scenario set-process <name> <proc> \
     [--container=<c>] [--script=<s>] [--interpreter=<i>] \
     [--enabled=<bool>] [--autorestart=<bool>] [--max-restarts=<n>] \
     [--restart-delay=<ms>] [--watch=<bool>]
bash ./platform.sh scenario add-process    <name> <proc> <script>
bash ./platform.sh scenario remove-process <name> <proc>
bash ./platform.sh scenario set-process-env    <name> <proc> <key> <value>
bash ./platform.sh scenario delete-process-env <name> <proc> <key>
bash ./platform.sh scenario set-container-env    <name> <container> <env>
bash ./platform.sh scenario delete-container-env <name> <container>

# Processes (pm2 — container from active scenario JSON)
bash ./platform.sh process list|start|stop|restart <name>
bash ./platform.sh process add <name> <script>
bash ./platform.sh process remove|move <name> [--to=<instance>]

# Database
bash ./platform.sh database migrate|seed|status [delivery|cbox|all]
bash ./platform.sh database clear --yes [mysql|redis|rabbitmq|all]

# Docker / top-level
bash ./platform.sh up [--scenario=<name>] [--no-migrate] [--no-seed]
bash ./platform.sh down --yes
bash ./platform.sh status                              # table: name/type/state/env/ports
bash ./platform.sh urls                               # labelled URLs + pm2 health per instance
bash ./platform.sh logs <instance|process>
bash ./platform.sh build [server|client|client-admin|cbox-web] [--node=<ver>]
bash ./platform.sh log view|clear
bash ./platform.sh tui
```

**Types:** `server mysql redis rabbitmq client client-admin cbox-web`  
**Envs:** `local development production test`

## Port Blocks

`host_port = base_host + (N-1) * block`

| Type | Internal | Base host | Block |
|------|----------|-----------|-------|
| `server` | 3000,3001,3002,3005,3026,3030 | same | 100 |
| `mysql` | 3306 | 3307 | 10 |
| `redis` | 6379 | 6380 | 10 |
| `rabbitmq` | 5672,15672 | 5673,15673 | 10 |
| `client` | 4200 | 4200 | 10 |
| `client-admin` | 4201 | 4201 | 10 |
| `cbox-web` | 4202 | 4202 | 10 |

Server container port → process (default scenario): `3000`=api-v1, `3001`=server.ts (main web API), `3002`=admin-dashboard, `3005`=auth, `3026`=mail-webhooks, `3030`=mobile-app.

## Process ports & env-var overrides

Each HTTP-serving process reads its port from a specific env var, falling back to a fixed default. **Code defaults** (the `|| N` fallback in each entry point):

| Process | Port env var | Default |
|---------|-------------|---------|
| `server.ts` (main web API) | `PORT` | 3000 |
| `api_v1.ts` (public/mobile API) | `API_V1_PORT` | 3001 |
| `admin_dashboard_server.ts` | `ADMIN_DASHBOARD_PORT` | 3002 |
| `auth.ts` | `AUTH_PORT` | 3005 |
| `order_updater_server.ts` | `ORDER_UPDATER_PORT` | 3021 |
| `shipping_points_server.ts` | `SHIPPING_POINTS_PORT` | 3022 |
| `mail_webhooks_server.ts` | `MAIL_WEBHOOKS_PORT` | 3026 |
| `mobile_app_server.ts` | `MOBILE_APP_PORT` | 3030 |
| `cbox_server.ts` / `cbox_public_server.ts` | `CBOX_INTERNAL_SERVER_PORT` / `CBOX_PUBLIC_SERVER_PORT` | 3035 / 3040 |
| `widget_server.ts` | `WIDGET_SERVER_PORT` | 3045 |

**Override precedence (per variable):** `scenario process env` > `server/.env.local` > code default. pm2 injects the scenario's `env` block into `process.env` before Node starts, and `dotenv` runs **without `override`** (see `config/environment.ts`), so a value pinned in the scenario wins over the local `.env`. Only the vars the scenario actually lists are pinned; everything else still comes from `.env.local`.

**Why the default scenario pins ports:** `server.ts` and `api_v1.ts` both run in `server-1`. `server.ts` (which owns `/auth/login`, the website backend) must be on the port the client targets (3001, the platform's "server API" convention), and `api_v1.ts` is moved off 3001 to the only other free exposed slot (3000). The pins make this deterministic regardless of any stray `PORT` in `server/.env.local`:
```json
{ "name": "server", "container": "server-1", "env": { "PORT": "3001" } }
{ "name": "api-v1", "container": "server-1", "env": { "API_V1_PORT": "3000" } }
```
If you co-locate `server.ts` with another HTTP process in a new scenario, pin their ports the same way so they don't collide on the generic `PORT`.

## Live reload (file watching)

Server `src/` is bind-mounted and pm2 watch is **on by default** for all processes. On Linux, chokidar uses inotify (~0% idle CPU). Efficiency settings: 1.5 s `watch_delay` debounce (rapid saves only trigger one restart) + `awaitWriteFinish` (waits for the write to settle, avoids partial-write false triggers).

To disable watch for a specific process in the scenario JSON set `"watch": false`. To disable entirely: `PM2_WATCH=0 bash ./platform.sh up`.

- Watching is scoped to `src/` with `ignore_watch` covering node_modules, dist, src/prisma, logs.
- **macOS/Windows:** bind mounts don't deliver inotify events, so `platform.sh` auto-detects the host (`uname`) and switches to polling (`WATCH_POLL=1` → chokidar `usePolling`). Override with `WATCH_POLL=1/0` in your shell (WSL on `/mnt/c` needs `1`); tune poll cadence with `WATCH_INTERVAL` (ms, default 2000). Linux uses native inotify.
- Angular clients reload independently via `ng serve` with the same host-detection logic.
- Angular clients reload independently via `ng serve`. Same host-detection as the server: on macOS/Windows `platform.sh` sets `NG_POLL` (ms) so `ng serve` polls; on Linux `NG_POLL` is empty and Angular uses its native event-driven watcher (~0% idle CPU). Force polling anywhere by setting `NG_POLL=<ms>` in the instance env file or shell (e.g. WSL on `/mnt/c`).

## Key Gotchas

**`up` / `scenario apply` create missing instances and auto-build images.** If a scenario references a container that doesn't exist, it's created automatically (type/number derived from the name, env from `container_envs` or `local`). If the required image (`platform-server`, `platform-client`, etc.) is missing, it is built inline before the container is created — no manual `build` step needed. `up` also auto-migrates and auto-seeds a fresh delivery DB after MySQL is ready; suppress with `--no-migrate` / `--no-seed`.

**Missing env vars crash server processes.** `.env.local` must include — beyond the URL vars — these three separate knex vars or every pm2 process hits `ECONNREFUSED 127.0.0.1:3306`:
```
DATABASE_HOST=mysql-1
DATABASE_USER=root
DATABASE_PASSWORD=localdev
```

**Rebuilt images don't refresh instance node_modules.** `server`/client instances mount a named volume over `/app/node_modules`. Docker seeds a named volume from the image **only once**, when it's first created empty — it never refreshes after an image rebuild. So after `build <type>`, existing instances of that type keep the **old** image's `node_modules` and may crash with confusing `Cannot find module ...` errors even though the image is fine. To pick up new/changed dependencies, recreate each affected instance (`instance delete <name> && instance create --type=<type> --num=<N>`) or remove its `${name}-node-modules` volume so it re-seeds. `build` now prints this reminder listing the affected instances.

**Client containers need the server source mounted.** All three Angular types (`client`, `client-admin`, `cbox-web`) bind-mount `$REPO_DIR/server/src:/server/src:ro` so TypeScript can resolve `@server/*` imports. This is already wired in `cmd-instance.sh` — just know it must stay there.

**pm2 `online` can hide a crash loop.** A process restarting every couple seconds still shows `online` in `pm2 list` / `instance pm2-status` between restarts. Judge health by the **restart count (`↺`) + uptime**, not the status word: a high/climbing restart count with sub-30s uptime means it's crash-looping. Diagnose with `./platform.sh logs <process>`. (`urls` annotates each process with its restart count for this reason.)

**`process` vs `instance` take different names.** `process <start|stop|restart> <name>` expects a **pm2 process name** (`api-v1`, `queue`), resolved to its container via the scenario JSON. `instance <start|stop|restart> <name>` expects a **container name** (`server-1`, `mysql-1`). Passing a container name to `process` errors with a hint pointing you to `instance`.

**Ad-hoc instances & scenario membership.** `instance create` offers to add a new instance to the active scenario's `infra` list when it isn't already part of it — accept so `up`/`down` manage it, or pass `--scenario-add` / `--no-scenario-add` to skip the prompt (auto-skipped when there's no TTY). `down` stops the active scenario's containers, then prompts to also stop any *running* instances that aren't in the scenario; `down --all` stops them without asking, `down --scenario-only` leaves them running.

**Stopped containers reconnect to the platform network on `up`.** When `up` starts a stopped container, `docker start` reconnects it to its stored network by ID. If the `platform` Docker network was deleted and recreated while the container was stopped (e.g. after `docker network prune`), the stored endpoint is stale — the container starts but ends up on no network while freshly-created containers land on the new `platform` network, breaking inter-container DNS. `up` guards against this by running `docker network connect platform <container>` after start (idempotent; errors suppressed).

**`database clear`** stops the container, removes it, deletes the data volume, then recreates the container. Recreating is part of the command.

**Inter-process comms are RabbitMQ-only.** No HTTP calls exist between server processes. The `LOCAL_*` URLs are only used by the Angular frontends.

**Frontend backend URLs come from the generated `server/src/config/urls.ts`** (gitignored; `entrypoint.sh` regenerates it on server-container boot from env vars). The Angular apps import these via `@server/config/urls`. Key exports:
- `LOCAL_SERVER_URL` / `LOCAL_DEV_SERVER_URL` / `LOCAL_ADMIN_DASHBOARD_SERVER_URL` → browser-facing — `http://localhost:<host-port>` (docker-published port, reachable from the user's machine).

**Adding a new `LOCAL_*` URL constant** means every environment's `urls.ts` must define it — `entrypoint.sh` covers local/docker, but a hand-maintained `urls.ts` (e.g. production) must add the same export or the Angular build fails to compile (`@server/*` resolves straight to `server/src`).

## Scenario JSON

```json
{
  "name": "default",
  "description": "...",
  "container_envs": { "server-1": "local" },
  "infra": [{ "name": "mysql-1" }, { "name": "redis-1" }],
  "processes": [{
    "name": "api-v1",
    "script": "src/api_v1.ts",
    "container": "server-1",
    "interpreter": "tsx",
    "enabled": true,
    "autorestart": true,
    "max_restarts": 10,
    "restart_delay": 2000,
    "watch": false,
    "env": {}
  }]
}
```

Files in `.scenarios/data/<name>.json`, bind-mounted read-only into server at `/scenarios/`.

## Key Files

| File | Role |
|------|------|
| `.scenarios/main.sh` | Bootstrap, globals, dispatch |
| `.scenarios/lib/instance-types.sh` | Port blocks, image map, `parse_instance_name`, `instance_port_flags` |
| `.scenarios/lib/docker-helpers.sh` | `list_instances`, `instance_state/type/env/is_running` |
| `.scenarios/cmd-instance.sh` | Instance lifecycle + mount definitions |
| `.scenarios/cmd-scenario.sh` | All scenario subcommands |
| `.scenarios/cmd-process.sh` | pm2 lifecycle via `docker exec` |
| `.scenarios/cmd-docker.sh` | `up/down/status/urls/build/logs/log` |
| `.scenarios/cmd-database.sh` | Prisma migrate/seed/clear/status |
| `.scenarios/scenario-json.sh` | All `_sc_*` JSON helpers (values via env vars, never string-interpolated) |
| `.scenarios/tui-editor.sh` | Scenario editor — all writes via CLI commands, no direct `_sc_*` calls |
| `.scenarios/tui-menus.sh` | `cmd_tui`, all menus |
