#!/usr/bin/env bash
# Connect the deployed VM to Grafana Cloud (run in Cloud Shell). Asks for the endpoint details and the access-policy
# token (hidden input), writes them to the VM's /opt/openwatch/.env, enables the `cloud` profile and starts Alloy.
#   PROJECT=openwatch-513308 bash scripts/deploy/grafana-cloud.sh
set -euo pipefail
PROJECT="${PROJECT:?set PROJECT=<your gcp project id>}"; ZONE="${ZONE:-us-central1-a}"; NAME="${NAME:-openwatch}"
echo "From grafana.com → your stack → Prometheus / Loki → Details:"
read -rp "  Prometheus remote-write URL (…/api/prom/push): " PROM_URL
read -rp "  Prometheus username / instance ID:            " PROM_USER
read -rp "  Loki URL (https://logs-prod-….grafana.net):   " LOKI_BASE
read -rp "  Loki user:                                    " LOKI_USER
read -rsp "  Access-policy token (metrics:write, logs:write; hidden): " TOKEN; echo
LOKI_URL="${LOKI_BASE%/}"; case "$LOKI_URL" in */loki/api/v1/push) ;; *) LOKI_URL="$LOKI_URL/loki/api/v1/push";; esac
for v in PROM_URL PROM_USER LOKI_URL LOKI_USER TOKEN; do [ -n "${!v}" ] || { echo "$v is empty" >&2; exit 1; }; done

# values travel over SSH stdin, never on a command line (so not in process lists or shell history)
printf '%s\n' "GRAFANA_CLOUD_PROM_URL=$PROM_URL" "GRAFANA_CLOUD_PROM_USER=$PROM_USER" "GRAFANA_CLOUD_LOKI_URL=$LOKI_URL" \
  "GRAFANA_CLOUD_LOKI_USER=$LOKI_USER" "GRAFANA_CLOUD_TOKEN=$TOKEN" "COMPOSE_PROFILES=cloud" |
gcloud compute ssh "$NAME" --zone "$ZONE" --project "$PROJECT" --command '
  set -e; cd /opt/openwatch; new=$(cat)
  for kv in $new; do k=${kv%%=*}; sudo sed -i "/^$k=/d" .env; done
  printf "%s\n" "$new" | sudo tee -a .env >/dev/null; sudo chmod 600 .env
  sudo git pull --ff-only -q && sudo docker compose pull -q && sudo docker compose up -d --no-build --force-recreate && sudo docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
  sleep 20; sudo docker compose logs --no-log-prefix --since 30s alloy 2>&1 | grep -iE "level=error.*(401|403|unauthor)" && echo "!! Grafana Cloud rejected the credentials" || echo "✓ Alloy running; data appears in Grafana Cloud within ~2 minutes"'
