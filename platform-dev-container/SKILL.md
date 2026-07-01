---
name: platform-dev-container
description: >-
  Scaffold and bring up a fully containerized, isolated colete-online platform dev
  stack in its own git worktree — a dedicated Docker container per branch with its
  own seeded MySQL/Redis/RabbitMQ, the Claude CLI + your skills inside, served on a
  host port, and reboot-surviving restart policies. Use this WHENEVER the user wants
  "a docker/dev container for the platform", "an isolated dev stack/sandbox", "spin
  up another dev docker like the others", "a containerized worktree", "a place to run
  the server / review a PR in isolation", or refers to the fable-N / dev-N style
  stacks — even if they don't say "skill". This is the colete-online-specific
  companion to `worktree-setup` (which it calls for the worktree + gitignored files):
  reach for `worktree-setup` when they just need a bare runnable worktree, and for
  THIS skill when they want that worktree wrapped in a running, isolated container.
  Do NOT use for non-platform projects or for a plain `git worktree`.
---

# platform-dev-container

Spin up an isolated, containerized colete-online dev environment in a worktree. Each
stack = a `server` container on a **private bridge network** reaching its **own**
MySQL (delivery+cbox) / Redis / RabbitMQ by container name, plus the Claude CLI +
your skills inside, served to the host on a port. Many can run side by side.

This skill exists because a bare worktree (`worktree-setup`) doesn't run the app in
isolation, and standing the container up by hand repeatedly trips the same handful of
non-obvious traps (RabbitMQ cookie race, Percona first-boot race, prisma OOM, the
egress-firewall-vs-internal-services conflict, reboot wiping no-policy containers).
The bundled files + script encode all of those fixes. Read `references/lessons.md`
for the *why* behind each — it's worth skimming before you change anything.

## Architecture (per stack)

```
host :PORT ──▶ server (private bridge coldev_<name>, 172.31.<N>.0/24)
                 │  reaches by container name:
                 ├─ col-local-mysql-<N>-delivery   (delivery_local, mobile_app, invoicing_system)
                 ├─ col-local-mysql-<N>-cbox        (cbox_local)
                 ├─ col-local-redis-<N>
                 └─ col-dev-rabbitmq-<N>            (dedicated, isolated)
```

Two compose services:
- **`dbsetup`** — host network + docker.sock. Runs the repo's `scripts/local.sh` to
  create/migrate/seed MySQL+Redis (which publish to host `127.0.0.1`, so it must be
  on the host network), starts the dedicated RabbitMQ, attaches them all to the
  private bridge, rewrites `.env.local` to the bridge hostnames, generates Prisma
  clients. Exits.
- **`server`** — the private bridge only. Runs the app, reaching the data tier by
  container name. `dbsetup` must complete first (`depends_on`).

## Inputs you need

1. **name** — short slug → worktree `platform-<name>`, image `colete-dev:<name>`,
   container `col-dev-<name>`, network `coldev_<name>`.
2. **branch** — new branch off `origin/development`, or an existing one.
3. **instance N** — a free `local.sh` instance number (1–99). Drives the data-tier
   container names + host-published ports (delivery `3306+N`, cbox `3406+N`, redis
   `6379+N`) and the bridge subnet `172.31.<N>.0/24`. **Pick a free one** (see below).
4. **firewall?** — block egress to `10.0.0.0/8` (VPN/internal). Default **off**.
   - **off (work stacks):** the server can reach internal services. Required if you
     want the server to actually *run* — it connects at boot to the lockers RabbitMQ
     at `10.10.0.122`, so with the firewall ON the app **crashes on startup**.
   - **on (review sandboxes):** for running untrusted/under-review code you want
     walled off from internal networks. Accept that the server app won't boot.
5. **seed?** — full seed (delivery+mobile_app+invoicing, ~15–20 min, realistic data)
   vs skip (empty migrated schemas, fast). Default **seed**.

## Workflow

### 1. Check what's free (always do this first)
```bash
# used instance numbers:
docker ps -a --format '{{.Names}}' | grep -oE 'col-local-mysql-[0-9]+' | grep -oE '[0-9]+$' | sort -un
# host ports for the chosen instance N (delivery 3306+N / cbox 3406+N / redis 6379+N) + app port:
ss -ltn | grep -oE ':(33[0-9][0-9]|34[0-9][0-9]|63[0-9][0-9]|30[0-9][0-9])\b' | sort -u
df -h /                         # each seeded stack ≈ 2–3 GB; bail if disk is tight
gh auth status                  # the seed pulls seed_data via gh
```
Pick a free instance and a free host app port. **Host `:3000` is taken by another
process on this machine** — don't map to it.

### 2. Scaffold + bring up
Use the bundled script — it creates the worktree (via the same steps as
`worktree-setup`), copies the gitignored per-worktree files, writes the three dev
files, and (with `--up`) brings the stack up with the retry + restart-policy logic:

```bash
SKILL=~/.claude/skills/platform-dev-container
"$SKILL/scripts/new-dev-stack.sh" \
  --name dev3 --branch dev-3 --instance 10 --app-port 3010 \
  --up            # add --firewall for a review sandbox; --no-seed to skip seeding
```
Run `new-dev-stack.sh --help` for all flags. Without `--up` it only scaffolds, and
prints the bring-up command to run yourself.

### 3. The bring-up gotcha you WILL hit (`--up` handles it; do it manually otherwise)
`dbsetup` can fail at step 3/6 on the **Percona cbox first-boot race**
(`ERROR 2002 ... mysql.sock` or `MySQL did not become ready within 60s`) — the cbox
container does an init-then-restart and the readiness check catches it mid-restart.
It is **transient**: the container is fine seconds later. **Just re-run the same
`docker compose ... up -d`** — `--up` retries automatically. (Seed is sentinel-guarded
in the `dev_state` volume, so a re-run won't re-seed.)

### 4. Verify + lock in
```bash
docker exec -u node col-dev-<name> true && echo "exec works"      # container is dev-able
# (server app: up only if firewall is OFF; otherwise it crashes on the lockers conn — expected)
```
`--up` already sets `docker update --restart unless-stopped` on the server **and** all
its data containers — **do this** (or it's done for you). Without it, **a host reboot
removes these containers entirely** (this host clears containers that have no restart
policy on boot — see lessons). With it, they come back with data intact, like the
older stacks.

### 5. Use it
```bash
docker exec -it -u node col-dev-<name> dev    # tmux + pre-authed Claude (your skills/plugins), in /app/server
docker exec -it -u node col-dev-<name> bash   # plain shell for build / prisma / tests / git
# app (firewall off): http://localhost:<app-port>
```
Always `-u node` (uid 1000 = host user) so files you/Claude touch stay yours, not
root's. The `dev` launcher forces `TERM=xterm-256color COLORTERM=truecolor` + `tmux -u`
so Claude's glyphs + diff colors render right.

## Claude-in-container

The server container mounts (read-only) your `~/.claude/skills`, `~/.claude/plugins`,
`~/.claude/statusline.py`, `~/.tmux.conf`, `~/.tmux`, and **seeds your
`~/.claude/.credentials.json`** into a persistent `claude_home` volume so Claude is
pre-authenticated with all your skills. Caveat: skills that hit `10.x` (Loki/
ClickHouse — log-search, *-health, perf-hunter, slow-endpoints, incident-trace, etc.)
**won't run inside a firewalled stack** (and only reach internal nets at all when the
firewall is off) — run those on the host.

## Browser testing (Playwright)
The image ships the Playwright **CLI** (`playwright` + `@playwright/test`) wired to the
Alpine **system Chromium** (`/usr/bin/chromium-browser`; PW's own browser builds don't
run on musl, so the download is skipped). There's deliberately **no Playwright MCP** —
the companion **`playwright-cli` skill** documents the launch recipe
(`executablePath` + `--no-sandbox --disable-dev-shm-usage`). So Claude-in-container can
run E2E/codegen/screenshots by shelling out, no extra server.

## Teardown
```bash
cd platform-<name> && docker compose -f docker-compose.dev.yml down
docker rm -f col-dev-rabbitmq-<N> col-local-mysql-<N>-delivery col-local-mysql-<N>-cbox col-local-redis-<N>
git worktree remove ../platform-<name>     # add --force if it refuses
```

## Reference
- `references/lessons.md` — every non-obvious fix and *why* (read before editing the templates).
- `assets/Dockerfile.dev`, `assets/docker-dev.sh` — copied verbatim into each stack (fully env-parameterized).
- The compose is generated per-stack by the script (host docker GID, ports, subnet, firewall/claude blocks vary).
