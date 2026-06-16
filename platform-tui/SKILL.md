---
name: platform-tui
description: Use when working with the platform repo's .scenarios/ CLI — running instance/scenario/process commands, or modifying the bash scripts in .scenarios/.
---

# Platform CLI Reference

Entry point: `bash ./platform.sh <command>` at repo root. Default (no args) = TUI.

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
bash ./platform.sh up [--scenario=<name>]
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

Server container port → process: `3000`=server(SSR), `3001`=api-v1, `3002`=admin-dashboard, `3005`=auth, `3026`=mail-webhooks, `3030`=mobile-app.

## Key Gotchas

**Missing env vars crash server processes.** `.env.local` must include — beyond the URL vars — these three separate knex vars or every pm2 process hits `ECONNREFUSED 127.0.0.1:3306`:
```
DATABASE_HOST=mysql-1
DATABASE_USER=root
DATABASE_PASSWORD=localdev
```

**Client containers need the server source mounted.** All three Angular types (`client`, `client-admin`, `cbox-web`) bind-mount `$REPO_DIR/server/src:/server/src:ro` so TypeScript can resolve `@server/*` imports. This is already wired in `cmd-instance.sh` — just know it must stay there.

**Stale `node_modules` volume → "Cannot find module".** Each server instance's `node_modules` lives in a Docker volume (`<instance>-node-modules`) that Docker seeds **only once**, on first run. Rebuilding the image (`platform.sh build server`) and pulling/merging a branch that adds a dependency do **NOT** refresh it. The new package is missing at runtime → a static `import` of it throws `Cannot find module 'X'`, which (combined with winston's exception handler) crash-loops the pm2 process — often masked as a crash "at shipping-point N" or a server that never binds its port. `scenario apply`/`up` runs `_check_node_deps` (in `cmd-scenario.sh`) which compares the container's `package.json` deps+devDeps against `node_modules` and **blocks pm2 apply with an actionable error** if any are missing. Fix:
```
docker exec <instance> sh -c 'cd /app && npm install --legacy-peer-deps'
```
(or recreate the instance to rebuild the volume). To pick up dep changes after a merge, run that `npm install` once per server instance.

**`database clear`** stops the container, removes it, deletes the data volume, then recreates the container. Recreating is part of the command.

**Inter-process comms are RabbitMQ-only.** No HTTP calls exist between server processes. `LOCAL_SERVER_URL` etc. are only used by Angular frontends (browser-side).

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
