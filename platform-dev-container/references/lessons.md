# Lessons — why the dev-stack templates look the way they do

Hard-won from building these stacks repeatedly. Read before editing the templates;
each item is a trap that cost real debugging time.

## Networking: two phases (host-net setup + private-bridge server)
`scripts/local.sh` creates the MySQL/Redis containers with `docker run -p 127.0.0.1:<port>`
and migrates them over that host loopback. So the step that runs `local.sh` **must be on
the host network** (`dbsetup`). But the running app should be on its **own** network
(so it can optionally be firewalled, and so stacks don't collide). Solution: `dbsetup`
(host net) creates the data tier, then `docker network connect`s those containers to a
private bridge; the `server` lives on that bridge and reaches them **by container name**.
`host.docker.internal` does NOT reach `127.0.0.1`-published ports from a bridge container —
that's why we attach the containers to the bridge instead.

## RabbitMQ `.erlang.cookie: eacces` (the cookie race)
The `rabbitmq` image's entrypoint runs as root, creates `/var/lib/rabbitmq/.erlang.cookie`
(mode 0400) and then drops to uid 999 — under load it sometimes reads the cookie as 999
before/when ownership is wrong → `Error when reading .../.erlang.cookie: eacces`, and the
broker exits during prelaunch (silent-ish, ~4s). It's intermittent and was maddening.
**Fix:** pre-seed a uid-999-owned, mode-0400 cookie into a persistent per-instance volume
(`coldev_rmq_<N>:/var/lib/rabbitmq`) so the broker reads an existing, correctly-owned cookie
and never races to create one. We also keep a small retry loop as a belt-and-suspenders.
(It is NOT a port conflict — the dedicated broker isn't published to the host.)

## Percona cbox first-boot race (the one you'll hit on every fresh stack)
Percona does an init-then-restart on first boot. `local.sh`'s readiness check can catch the
**cbox** container mid-restart → step 3/6 dies with `ERROR 2002 ... mysql.sock` or
`MySQL did not become ready within 60s`. **Transient** — the container is healthy seconds
later. The fix is operational, not code: **re-run the same `docker compose ... up -d`.**
Seeding is sentinel-guarded (`/dev-state/seeded`), so the re-run won't re-seed. `--up`
retries up to 4×.

## prisma-generate SIGSEGV under memory pressure
The image sets `NODE_OPTIONS=--max-old-space-size=8192` (needed for the big server build),
but with several stacks running, `tsc --build` for the prisma types can SIGSEGV (exit 139)
trying to grow toward 8 GB. **Fix:** run just the `prisma-generate` step with
`NODE_OPTIONS=--max-old-space-size=3072` — ample for the types build, fits available RAM.

## The egress firewall vs the server actually booting (important)
The optional `iptables -A OUTPUT -d 10.0.0.0/8 -j REJECT` (for review sandboxes) **also
blocks the server's boot-time connection to the hardcoded lockers RabbitMQ at
`10.10.0.122`** (`RABBITMQ_LOGIN_LOCKERS` in `constants.ts`), so the app **crashes on
startup** (exit 1, silent). So:
- **Work stacks → FIREWALL=0** (default). Server can boot and reach internal services.
- **Review sandboxes → FIREWALL=1.** Accept the app won't run; you get an isolated
  container (exec/Claude/build still work) walled off the VPN.
Also: skills that hit `10.x` (Loki/ClickHouse: log-search, *-health, perf-hunter,
slow-endpoints, incident-trace) only work when the firewall is off — otherwise run them
on the host. When FIREWALL=1 the `server` service needs `user: "0:0"` + `cap_add: NET_ADMIN`
(root to install the rule, then it `su-exec`s down to uid 1000); when 0, it runs as node.

## Ownership: run as uid 1000, keep the host worktree yours
The container runs as `node` (uid 1000 == the host user), so files written into the
bind-mounted worktree stay owned by you. `dbsetup` runs as root (needs docker.sock) and
`chown -R 1000:1000`s the volumes + generated files at the end. The named-volume
mountpoints are pre-created + chowned to `node` in the Dockerfile, or empty volumes mount
root-owned and `npm ci` fails with EACCES. Always `docker exec -u node …`.

## tmux/Claude glyphs + colors
`docker exec` gives a bare `TERM=xterm` with no `RGB`, so tmux strips truecolor and Claude
falls back to bright ANSI (eye-searing diffs), and on Alpine/musl tmux needs `-u` or it
renders `⏺`/`⎿` as `_`. The baked `dev` launcher sets `TERM=xterm-256color
COLORTERM=truecolor` + `tmux -u` to fix both. `git` inside needs the repo `.git` common
dir mounted (the worktree's `.git` is a pointer to `<main>/.git/worktrees/<name>`) +
`safe.directory`, or the statusLine branch is blank and `git` errors.

## Reboots remove no-restart-policy containers (this host)
On this machine, a reboot **removes** containers that have no restart policy (their data/
anon volumes go with them — the seed is lost), while `restart: unless-stopped` containers
come back **with data intact**. Named volumes (node_modules, prisma clients, claude_home)
and images survive regardless. So always `docker update --restart unless-stopped` the
server + its data tier (`--up` does this). After a reboot: the policy'd containers
auto-return; any that were removed must be recreated via `docker compose up -d` (which
re-seeds unless the `dev_state` sentinel volume survived — if it survived but the MySQL
data didn't, delete the sentinel to force a real re-seed, or accept empty schemas).

## Host port :3000
Taken by an unrelated process on this host — never map a stack's app to `:3000`. Default is
`3000 + instance`; the script verifies it's free.

## Disk
Each fully-seeded stack ≈ 2–3 GB (node_modules volume + MySQL data + image layers), and a
build regenerates ~8 GB of transient build cache. Check `df -h /` first; prune build cache
(`docker builder prune -af`) after builds when disk is tight.
