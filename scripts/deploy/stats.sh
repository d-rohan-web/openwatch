#!/usr/bin/env bash
# Live visitor dashboard for the deployed site (run in Cloud Shell): unique visitors, pages, referrers, countries,
# browsers, from Caddy's access log on the VM. Nothing leaves the VM; no third-party analytics. q quits.
#   PROJECT=openwatch-513308 bash scripts/deploy/stats.sh
set -euo pipefail
PROJECT="${PROJECT:?set PROJECT=<your gcp project id>}"; ZONE="${ZONE:-us-central1-a}"; NAME="${NAME:-openwatch}"
gcloud compute ssh "$NAME" --zone "$ZONE" --project "$PROJECT" -- -t \
  'cd /opt/openwatch && sudo docker compose logs caddy --no-log-prefix --no-color 2>/dev/null | grep "\"request\"" |
   sudo docker run --rm -i -e TERM=xterm-256color -e LANG=C.UTF-8 allinurl/goaccess:1.9.3 - --log-format=CADDY \
     --ignore-crawlers --ignore-panel=REMOTE_USER --ignore-status=101 --anonymize-ip'
