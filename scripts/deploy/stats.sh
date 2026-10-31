#!/usr/bin/env bash
# Visitor report for the deployed site (run in Cloud Shell): unique visitors, pages, referrers, countries, browsers,
# built from Caddy's access log on the VM with GoAccess. IPs anonymised; nothing goes to third parties.
# Downloads openwatch-stats.html to your browser (Cloud Shell), or leaves it in the current folder.
#   PROJECT=openwatch-513308 bash scripts/deploy/stats.sh            # everything kept (up to 90 days)
#   PROJECT=openwatch-513308 DAYS=7 bash scripts/deploy/stats.sh     # last 7 days only
set -euo pipefail
PROJECT="${PROJECT:?set PROJECT=<your gcp project id>}"; ZONE="${ZONE:-us-central1-a}"; NAME="${NAME:-openwatch}"
OUT="${OUT:-openwatch-stats.html}"; DAYS="${DAYS:-0}"
case "$DAYS" in ''|*[!0-9]*) echo "DAYS must be a number" >&2; exit 1;; esac
KEEP=$([ "$DAYS" -gt 0 ] && echo "--keep-last=$DAYS" || true)
gcloud compute ssh "$NAME" --zone "$ZONE" --project "$PROJECT" --command "
  cd /opt/openwatch && sudo docker compose exec -T caddy sh -c 'for f in /data/access*; do case \$f in *.gz) zcat \$f;; *) cat \$f;; esac; done' 2>/dev/null | grep '\"request\"' |
  sudo docker run --rm -i allinurl/goaccess:1.9.3 - --log-format=CADDY --ignore-crawlers --ignore-status=101 \
    --anonymize-ip $KEEP --html-report-title='OpenWatch visitors' > /tmp/openwatch-stats.html"
gcloud compute scp "$NAME:/tmp/openwatch-stats.html" "$OUT" --zone "$ZONE" --project "$PROJECT"
if command -v cloudshell >/dev/null; then cloudshell download "$OUT"; else echo "report: $PWD/$OUT"; fi
