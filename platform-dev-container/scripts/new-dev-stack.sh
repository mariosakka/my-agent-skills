#!/usr/bin/env bash
# new-dev-stack.sh — scaffold (and optionally bring up) an isolated, containerized
# colete-online dev stack in a git worktree. See ../SKILL.md and ../references/lessons.md.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM_MAIN="${PLATFORM_MAIN:-/home/alex/Work/colete-online/platform}"

usage() {
  cat <<'EOF'
Usage:
  new-dev-stack.sh --name <slug> --branch <branch> --instance <N> [options]

Required:
  --name <slug>       worktree=platform-<slug>, image=colete-dev:<slug>,
                      container=col-dev-<slug>, network=coldev_<slug>
  --branch <branch>   branch to create off origin/development (or existing)
  --instance <N>      free local.sh instance (1-99): DB/redis/rabbitmq names +
                      host ports (delivery 3306+N / cbox 3406+N / redis 6379+N) +
                      bridge subnet 172.31.<N>.0/24

Options:
  --app-port <P>      host port → container :3000 (default 3000+N; must be free, ≠3000)
  --branch-exists     check out an existing branch instead of creating a new one
  --firewall          block egress to 10.0.0.0/8 (review sandbox; server WON'T boot)
  --no-claude         don't mount your ~/.claude skills/plugins/creds + tmux config
  --no-seed           skip DB seeding (empty migrated schemas; fast)
  --up                build + bring the stack up after scaffolding (retries the
                      Percona cbox race, sets restart policies, verifies)
  --repo <path>       platform main checkout (default $PLATFORM_MAIN)
  -h, --help
EOF
  exit "${1:-0}"
}

NAME="" BRANCH="" INSTANCE="" APP_PORT="" BRANCH_EXISTS=0 FIREWALL=0 CLAUDE=1 NO_SEED=0 DO_UP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --branch) BRANCH="$2"; shift 2;;
    --instance) INSTANCE="$2"; shift 2;;
    --app-port) APP_PORT="$2"; shift 2;;
    --branch-exists) BRANCH_EXISTS=1; shift;;
    --firewall) FIREWALL=1; shift;;
    --no-claude) CLAUDE=0; shift;;
    --no-seed) NO_SEED=1; shift;;
    --up) DO_UP=1; shift;;
    --repo) PLATFORM_MAIN="$2"; shift 2;;
    -h|--help) usage 0;;
    *) echo "Unknown arg: $1" >&2; usage 1;;
  esac
done
[ -n "$NAME" ] && [ -n "$BRANCH" ] && [ -n "$INSTANCE" ] || { echo "ERROR: --name, --branch, --instance are required" >&2; usage 1; }
[[ "$INSTANCE" =~ ^[0-9]+$ ]] && [ "$INSTANCE" -ge 1 ] && [ "$INSTANCE" -le 99 ] || { echo "ERROR: --instance must be 1-99" >&2; exit 1; }
[ -d "$PLATFORM_MAIN/.git" ] || { echo "ERROR: platform main checkout not found at $PLATFORM_MAIN (use --repo)" >&2; exit 1; }

PARENT="$(dirname "$PLATFORM_MAIN")"
WT="$PARENT/platform-$NAME"
APP_PORT="${APP_PORT:-$((3000 + INSTANCE))}"
SUBNET="172.31.${INSTANCE}.0/24"
NET="coldev_${NAME}"
SERVER_C="col-dev-${NAME}"
SETUP_C="col-dev-${NAME}-setup"
IMAGE="colete-dev:${NAME}"
COMPOSE="$WT/docker-compose.dev.yml"
DOCKER_GID="$(getent group docker 2>/dev/null | cut -d: -f3)"; DOCKER_GID="${DOCKER_GID:-997}"
HOME_DIR="${HOME:-/home/alex}"

# ── pre-flight: collisions ──────────────────────────────────
echo "▸ pre-flight checks"
[ -e "$WT" ] && { echo "ERROR: $WT already exists" >&2; exit 1; }
for n in "$SERVER_C" "$SETUP_C" "col-local-mysql-${INSTANCE}-delivery" "col-dev-rabbitmq-${INSTANCE}"; do
  docker inspect "$n" >/dev/null 2>&1 && { echo "ERROR: container $n already exists — instance $INSTANCE is in use" >&2; exit 1; }
done
if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -qE ":${APP_PORT}\b"; then
  echo "ERROR: host port $APP_PORT is in use — pass a free --app-port" >&2; exit 1
fi
echo "  name=$NAME instance=$INSTANCE app-port=$APP_PORT subnet=$SUBNET firewall=$FIREWALL claude=$CLAUDE seed=$([ $NO_SEED = 1 ] && echo no || echo yes)"

# ── 1. worktree (same as worktree-setup) + gitignored per-worktree files ──
echo "▸ creating worktree $WT on branch $BRANCH"
git -C "$PLATFORM_MAIN" fetch origin development --quiet || true
if [ "$BRANCH_EXISTS" = 1 ]; then
  git -C "$PLATFORM_MAIN" worktree add "$WT" "$BRANCH"
else
  git -C "$PLATFORM_MAIN" worktree add -b "$BRANCH" "$WT" origin/development
fi
echo "▸ copying gitignored per-worktree files"
cp "$PLATFORM_MAIN/server/.env.development"               "$WT/server/.env.development"
cp "$PLATFORM_MAIN/server/src/config/urls.ts"             "$WT/server/src/config/urls.ts"
cp "$PLATFORM_MAIN/server/src/config/rabbitmq_constants.ts" "$WT/server/src/config/rabbitmq_constants.ts"

# ── 2. the two verbatim dev files ──
cp "$SKILL_DIR/assets/Dockerfile.dev" "$WT/server/Dockerfile.dev"
cp "$SKILL_DIR/assets/docker-dev.sh"  "$WT/server/docker-dev.sh"

# ── 3. generate the per-stack compose ──
echo "▸ writing docker-compose.dev.yml"
# server-service extras that depend on flags:
fw_lines=""
[ "$FIREWALL" = 1 ] && fw_lines=$'    user: "0:0"\n    cap_add:\n      - NET_ADMIN'
claude_lines=""
if [ "$CLAUDE" = 1 ]; then
  claude_lines=$(cat <<EOF
      - $PLATFORM_MAIN/.git:$PLATFORM_MAIN/.git
      - $HOME_DIR/.tmux.conf:/home/node/.tmux.conf:ro
      - $HOME_DIR/.tmux:/home/node/.tmux:ro
      - $HOME_DIR/.claude/statusline.py:/home/node/.claude/statusline.py:ro
      - $HOME_DIR/.claude/.credentials.json:/seed/credentials.json:ro
      - $HOME_DIR/.claude/skills:/home/node/.claude/skills:ro
      - $HOME_DIR/.claude/plugins:/home/node/.claude/plugins:ro
      - claude_home:/home/node/.claude
EOF
)
fi

cat > "$COMPOSE" <<EOF
# Generated by the platform-dev-container skill. Stack: $NAME (instance $INSTANCE).
#   GH_TOKEN="\$(gh auth token)" docker compose -f docker-compose.dev.yml up -d
#   docker exec -it -u node $SERVER_C dev      # tmux + Claude
services:
  dbsetup:
    build: { context: ./server, dockerfile: Dockerfile.dev }
    image: $IMAGE
    container_name: $SETUP_C
    init: true
    network_mode: host
    group_add: ["$DOCKER_GID"]
    environment:
      NODE_ENV: local
      INSTANCE: "$INSTANCE"
      DEV_NET: $NET
      NO_SEED: "$NO_SEED"
      GH_TOKEN: \${GH_TOKEN:-}
      DEV_RABBITMQ_USER: dev
      DEV_RABBITMQ_PASS: dev
      HOME: /home/node
    working_dir: /app/server
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
      - server_node_modules:/app/server/node_modules
      - prisma_cbox:/app/server/src/prisma/cbox/generated
      - prisma_delivery:/app/server/src/prisma/delivery/generated
      - prisma_mobile:/app/server/src/prisma/mobile_app/generated
      - prisma_invoicing:/app/server/src/prisma/invoicing_system/generated
      - prisma_types:/app/server/src/prisma-types
      - dev_state:/dev-state
    command: ["bash", "/app/server/docker-dev.sh", "setup"]

  server:
    image: $IMAGE
    container_name: $SERVER_C
    init: true
    depends_on:
      dbsetup: { condition: service_completed_successfully }
    networks: [coldev]
$fw_lines
    environment:
      NODE_ENV: local
      INSTANCE: "$INSTANCE"
      DEV_NET: $NET
      FIREWALL: "$FIREWALL"
      GH_TOKEN: \${GH_TOKEN:-}
      DEV_RABBITMQ_USER: dev
      DEV_RABBITMQ_PASS: dev
      HOME: /home/node
      LANG: C.UTF-8
      LC_ALL: C.UTF-8
    working_dir: /app/server
    volumes:
      - .:/app
      - server_node_modules:/app/server/node_modules
      - prisma_cbox:/app/server/src/prisma/cbox/generated
      - prisma_delivery:/app/server/src/prisma/delivery/generated
      - prisma_mobile:/app/server/src/prisma/mobile_app/generated
      - prisma_invoicing:/app/server/src/prisma/invoicing_system/generated
      - prisma_types:/app/server/src/prisma-types
      - dev_state:/dev-state
$claude_lines
    command: ["bash", "/app/server/docker-dev.sh", "serve"]
    ports:
      - "127.0.0.1:$APP_PORT:3000"
    stdin_open: true
    tty: true

networks:
  coldev:
    name: $NET
    ipam:
      config:
        - subnet: $SUBNET

volumes:
  server_node_modules:
  prisma_cbox:
  prisma_delivery:
  prisma_mobile:
  prisma_invoicing:
  prisma_types:
  dev_state:
  claude_home:
EOF

# keep the dev files out of `git status` (worktree-local exclude)
EXCL="$(git -C "$WT" rev-parse --git-path info/exclude)"
for f in docker-compose.dev.yml server/Dockerfile.dev server/docker-dev.sh; do
  grep -qxF "$f" "$EXCL" 2>/dev/null || echo "$f" >> "$EXCL"
done

echo "▸ scaffolded $WT"
docker compose -f "$COMPOSE" config --quiet && echo "  compose validates ✓"

if [ "$DO_UP" != 1 ]; then
  echo
  echo "Next:  GH_TOKEN=\"\$(gh auth token)\" docker compose -f $COMPOSE up -d"
  echo "       (re-run that same command if dbsetup hits the Percona cbox race; then"
  echo "        docker update --restart unless-stopped on the server + data containers)"
  exit 0
fi

# ── 4. bring up, retrying the transient Percona cbox first-boot race ──
echo "▸ building + bringing up (this seeds on first boot; ~15-20 min)"
export GH_TOKEN="$(gh auth token 2>/dev/null || true)"
docker compose -f "$COMPOSE" build >/dev/null
ok=0
for try in 1 2 3 4; do
  docker compose -f "$COMPOSE" up -d || true
  while [ "$(docker inspect -f '{{.State.Status}}' "$SETUP_C" 2>/dev/null)" = "running" ]; do sleep 5; done
  ec="$(docker inspect -f '{{.State.ExitCode}}' "$SETUP_C" 2>/dev/null || echo 1)"
  if [ "$ec" = "0" ]; then ok=1; break; fi
  echo "  dbsetup exit=$ec (likely the transient Percona cbox race) — retry $try/4…"
done
[ "$ok" = 1 ] || { echo "ERROR: dbsetup kept failing; inspect 'docker logs $SETUP_C'" >&2; exit 1; }

# ── 5. restart policies so a reboot keeps them WITH data (this host removes
#       no-restart-policy containers on boot) ──
echo "▸ setting restart policies (survive reboots with data intact)"
for c in "$SERVER_C" \
  "col-local-mysql-${INSTANCE}-delivery" "col-local-mysql-${INSTANCE}-cbox" \
  "col-local-redis-${INSTANCE}" "col-dev-rabbitmq-${INSTANCE}"; do
  docker update --restart unless-stopped "$c" >/dev/null 2>&1 && echo "  $c" || true
done

# ── 6. verify ──
if docker exec -u node "$SERVER_C" true 2>/dev/null; then
  echo "✓ $SERVER_C is up and dev-able:  docker exec -it -u node $SERVER_C dev"
  [ "$FIREWALL" = 1 ] && echo "  (firewall ON → the server app crashes on the lockers conn by design; the container stays up for exec)"
else
  echo "! $SERVER_C not exec-ready — check 'docker logs $SERVER_C'"
fi
