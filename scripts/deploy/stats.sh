#!/usr/bin/env bash
# Visitor report for the deployed site (run in Cloud Shell): unique visitors, pages, referrers, countries, browsers,
# built from Caddy's access log on the VM with GoAccess. IPs anonymised; nothing goes to third parties.
# Produces openwatch-stats.html and downloads it to your browser (Cloud Shell), or leaves it in the current folder.
#   PROJECT=openwatch-513308 bash scripts/deploy/stats.sh
set -euo pipefail
PROJECT="${PROJECT:?set PROJECT=<your gcp project id>}"; ZONE="${ZONE:-us-central1-a}"; NAME="${NAME:-openwatch}"
OUT="${OUT:-openwatch-stats.html}"
gcloud compute ssh "$NAME" --zone "$ZONE" --project "$PROJECT" --command \
  'cd /opt/openwatch && sudo docker compose logs caddy --no-log-prefix --no-color 2>/dev/null | grep "\"request\"" |
   sudo docker run --rm -i allinurl/goaccess:1.9.3 - --log-format=CADDY --ignore-crawlers --ignore-status=101 \
     --anonymize-ip --html-report-title="OpenWatch visitors" > /tmp/openwatch-stats.html'
gcloud compute scp "$NAME:/tmp/openwatch-stats.html" "$OUT" --zone "$ZONE" --project "$PROJECT"
if command -v cloudshell >/dev/null; then cloudshell download "$OUT"; else echo "report: $PWD/$OUT"; fi
