#!/usr/bin/env bash
# docker-dev.sh — driver for the fully-containerized, network-isolated dev stack.
#
#   docker-dev.sh setup   (dbsetup service, host network, runs once)
#   docker-dev.sh serve   (server service, private bridge, long-running app)
#
# Why two phases:
#   The repo's scripts/local.sh creates MySQL/Redis as containers published to the
#   host's 127.0.0.1 and migrates them over that loopback — so it must run in a
#   host-network context (`setup`). The app runs on a private bridge (`serve`),
#   reaching the DB/Redis/RabbitMQ that `setup` attached to that bridge by name.
#   Optionally (FIREWALL=1) the app is also walled off the VPN/internal 10.0.0.0/8.
#
# Env (set by docker-compose.dev.yml): INSTANCE, DEV_NET, DEV_RABBITMQ_USER/PASS,
#   FIREWALL (0/1, default 0).
set -euo pipefail

MODE="${1:-serve}"
INSTANCE="${INSTANCE:-1}"
NET="${DEV_NET:-coldev_${INSTANCE}}"
RMQ_USER="${DEV_RABBITMQ_USER:-dev}"
RMQ_PASS="${DEV_RABBITMQ_PASS:-dev}"
FIREWALL="${FIREWALL:-0}"

DELIVERY_C="col-local-mysql-${INSTANCE}-delivery"
CBOX_C="col-local-mysql-${INSTANCE}-cbox"
REDIS_C="col-local-redis-${INSTANCE}"
RMQ_C="col-dev-rabbitmq-${INSTANCE}"

step() { printf '\n\033[1;36m▸ %s\033[0m\n' "$*"; }

# ─────────────────────────────────────────────────────────────
# setup — host network, has docker.sock; runs as root.
# ─────────────────────────────────────────────────────────────
setup() {
  cd /app/server
  export NODE_ENV=local

  step "[1/6] Installing dependencies (npm ci) if needed"
  if [ ! -x node_modules/.bin/tsx ]; then
    npm ci --legacy-peer-deps
  else
    echo "  node_modules volume already populated — skipping"
  fi

  step "[2/6] Ensuring private bridge network ($NET) + isolated RabbitMQ ($RMQ_C)"
  docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null

  # Pre-seed a uid-999-owned, 0400 .erlang.cookie in a persistent volume. RabbitMQ's
  # entrypoint otherwise CREATES the cookie as root (0400) before dropping to the
  # rabbitmq user (uid 999), which then can't read it → ".erlang.cookie: eacces"
  # crash at boot (a race the host loses under load). Pre-seeding = deterministic boot.
  RMQ_VOL="coldev_rmq_${INSTANCE}"
  docker volume create "$RMQ_VOL" >/dev/null
  docker run --rm -v "$RMQ_VOL":/d alpine sh -c \
    "test -f /d/.erlang.cookie || printf '%s' 'COLDEVRMQCOOKIE${INSTANCE}PADDING00' > /d/.erlang.cookie; \
     chown 999:999 /d/.erlang.cookie; chmod 400 /d/.erlang.cookie" >/dev/null

  # Not published to the host → no clash with a host RabbitMQ on :5672. Retry anyway.
  rmq_ready=false
  for attempt in 1 2 3 4 5; do
    if [ -n "$(docker ps -q -f "name=^/${RMQ_C}$")" ] \
       && docker exec "$RMQ_C" rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
      rmq_ready=true; break
    fi
    docker rm -f "$RMQ_C" >/dev/null 2>&1 || true
    docker run -d --name "$RMQ_C" --hostname "$RMQ_C" --network "$NET" \
      -v "$RMQ_VOL":/var/lib/rabbitmq \
      -e RABBITMQ_DEFAULT_USER="$RMQ_USER" -e RABBITMQ_DEFAULT_PASS="$RMQ_PASS" \
      rabbitmq:3-management >/dev/null
    printf '  waiting for rabbitmq (attempt %s/5)' "$attempt"
    for _ in $(seq 1 45); do
      if docker exec "$RMQ_C" rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
        rmq_ready=true; printf ' ready\n'; break
      fi
      [ -z "$(docker ps -q -f "name=^/${RMQ_C}$")" ] && { printf ' crashed, retrying\n'; break; }
      printf '.'; sleep 1
    done
    [ "$rmq_ready" = true ] && break
  done
  if [ "$rmq_ready" != true ]; then
    echo "  ERROR: RabbitMQ ($RMQ_C) did not become ready after 5 attempts — aborting." >&2
    docker logs "$RMQ_C" 2>&1 | tail -15 >&2 || true
    exit 1
  fi

  step "[3/6] Creating + migrating + seeding MySQL/Redis via scripts/local.sh (instance $INSTANCE)"
  # NOTE: Percona's cbox container does an init-then-restart on first boot; local.sh's
  # readiness check can catch it mid-restart → "ERROR 2002 ... mysql.sock" / "did not
  # become ready within 60s" and this step aborts. It is TRANSIENT — just re-run the
  # whole `docker compose ... up -d`; the cbox container is fine seconds later.
  SEED=()
  if [ ! -f /dev-state/seeded ] && [ "${NO_SEED:-0}" != "1" ]; then
    SEED+=(--seed); echo "  first boot → seeding delivery + mobile_app + invoicing"
  else
    echo "  skipping seed (already seeded or NO_SEED=1)"
  fi
  NODE_ENV=local ./scripts/local.sh start --instance="$INSTANCE" "${SEED[@]}"
  [ ${#SEED[@]} -gt 0 ] && touch /dev-state/seeded || true

  step "[4/6] Attaching DB/Redis containers to $NET (reachable by name from the app)"
  for c in "$DELIVERY_C" "$CBOX_C" "$REDIS_C"; do
    docker network connect "$NET" "$c" 2>/dev/null && echo "  + $c" || echo "  = $c (already attached)"
  done

  step "[5/6] Rewriting .env.local for the bridge (container-name hosts, internal ports)"
  # local-env.sh wrote 127.0.0.1 URLs (for setup's own migrate); the app talks over
  # the bridge, so repoint at container names + the internal default ports.
  printf 'export const USE_LOCAL_RABBITMQ = false;\n' > src/config/rabbitmq_constants.ts
  upsert() {
    if grep -q "^$1=" .env.local; then sed -i "s|^$1=.*|$1=$2|" .env.local
    else printf '%s=%s\n' "$1" "$2" >> .env.local; fi
  }
  upsert DELIVERY_DATABASE_URL   "mysql://root:localdev@${DELIVERY_C}:3306/delivery_local"
  upsert CBOX_DATABASE_URL       "mysql://root:localdev@${CBOX_C}:3306/cbox_local"
  upsert MOBILE_APP_DATABASE_URL "mysql://root:localdev@${DELIVERY_C}:3306/mobile_app"
  upsert INVOICING_DATABASE_URL  "mysql://root:localdev@${DELIVERY_C}:3306/invoicing_system"
  upsert DATABASE_HOST           "${DELIVERY_C}"
  upsert DATABASE_USER           "root"
  upsert DATABASE_PASSWORD       "localdev"
  upsert REDIS_URL               "redis://${REDIS_C}:6379"
  upsert REDIS_PASSWORD          "localdev"
  upsert RABBITMQ_HOST           "${RMQ_C}"
  upsert RABBITMQ_USER           "${RMQ_USER}"
  upsert RABBITMQ_PASSWORD       "${RMQ_PASS}"
  upsert PORT                    "3000"

  step "[6/6] Generating Prisma clients + types, then handing ownership back to uid 1000"
  # Cap the tsc heap: the image default (8 GB) can SIGSEGV under memory pressure when
  # several stacks run; the prisma-types build fits comfortably in 3 GB.
  NODE_ENV=local NODE_OPTIONS=--max-old-space-size=3072 npm run prisma-generate
  chown -R 1000:1000 \
    node_modules src/prisma/cbox/generated src/prisma/delivery/generated \
    src/prisma/mobile_app/generated src/prisma/invoicing_system/generated \
    src/prisma-types dist /dev-state 2>/dev/null || true
  chown 1000:1000 .env.local src/config/rabbitmq_constants.ts 2>/dev/null || true
  echo "  setup complete"
}

# ─────────────────────────────────────────────────────────────
# serve — private bridge; runs as root only if FIREWALL=1 (to set iptables),
# then drops to the unprivileged user (uid 1000) to run the app.
# ─────────────────────────────────────────────────────────────
serve() {
  step "[1/3] Provisioning Claude config (persistent volume) + git"
  mkdir -p /home/node/.claude
  chown node:node /home/node/.claude 2>/dev/null || true
  if [ ! -f /home/node/.claude/.credentials.json ] && [ -f /seed/credentials.json ]; then
    cp /seed/credentials.json /home/node/.claude/.credentials.json
    chown node:node /home/node/.claude/.credentials.json 2>/dev/null && chmod 600 /home/node/.claude/.credentials.json
    echo "  seeded Claude credentials (pre-authenticated)"
  fi
  if [ ! -f /home/node/.claude/settings.json ]; then
    printf '{\n  "statusLine": { "type": "command", "command": "python3 /home/node/.claude/statusline.py" }\n}\n' \
      > /home/node/.claude/settings.json
    chown node:node /home/node/.claude/settings.json 2>/dev/null || true
  fi
  su-exec node:node git config --global --add safe.directory /app/server 2>/dev/null || true

  if [ "$FIREWALL" = "1" ]; then
    step "[2/3] Firewalling egress to VPN/internal 10.0.0.0/8 (REJECT)"
    # NOTE: this BLOCKS the server's boot-time connection to the lockers RabbitMQ at
    # 10.10.0.122 → the app crashes on startup. That's expected/acceptable for a
    # review sandbox (you want it walled off). For a WORK stack leave FIREWALL=0.
    if iptables -C OUTPUT -d 10.0.0.0/8 -j REJECT 2>/dev/null; then
      echo "  rule already present"
    elif iptables -A OUTPUT -d 10.0.0.0/8 -j REJECT 2>/dev/null; then
      echo "  blocked 10.0.0.0/8"
    else
      echo "  ERROR: could not install iptables rule (is cap_add: NET_ADMIN set?)" >&2
      exit 1
    fi
  else
    step "[2/3] Egress firewall disabled (work stack — server reaches internal services)"
  fi

  step "[3/3] Starting server (NODE_ENV=local) on :3000 as uid 1000"
  cd /app/server
  exec su-exec 1000:1000 env NODE_ENV=local npm run serve
}

case "$MODE" in
  setup) setup ;;
  serve) serve ;;
  *) echo "usage: docker-dev.sh {setup|serve}" >&2; exit 1 ;;
esac
