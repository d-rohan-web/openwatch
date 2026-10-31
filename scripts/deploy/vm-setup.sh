#!/usr/bin/env bash
# Runs on the VM as its startup script (every boot; idempotent): Docker, swap, code, config, start.
# Reads the site name from instance metadata `openwatch-site` (set by gcp.sh).
set -euxo pipefail
REPO=https://github.com/d-rohan-web/openwatch.git
DIR=/opt/openwatch
meta() { curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" || true; }

command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh      # official Docker install script

# 1 GB RAM: add 2 GB swap so builds/spikes never OOM-kill the collector
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q /swapfile /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

[ -d "$DIR/.git" ] && git -C "$DIR" pull --ff-only || git clone --depth 1 "$REPO" "$DIR"
cd "$DIR"
[ -f .env ] || cp .env.example .env
set_env() { grep -q "^$1=" .env && sed -i "s|^$1=.*|$1=$2|" .env || echo "$1=$2" >> .env; }
SITE=$(meta openwatch-site)
[ -n "$SITE" ] && set_env OPENWATCH_SITE "$SITE"
set_env OPENWATCH_HTTPS_PORT 443
set_env OPENWATCH_HTTP_PORT 80

docker compose pull
docker compose up -d --no-build --remove-orphans
# Caddy reads its config at start: reload gracefully so Caddyfile changes from git apply without downtime
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile || true

# daily update at 04:00 IST (22:30 UTC): newest main images, prune old ones
cat > /etc/cron.d/openwatch-update <<CRON
30 22 * * * root cd $DIR && git pull --ff-only -q && docker compose pull -q && docker compose up -d --no-build --remove-orphans && docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; docker image prune -f >/dev/null
CRON
