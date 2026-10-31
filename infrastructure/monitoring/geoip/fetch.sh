#!/bin/sh
# Download the free DB-IP "IP to City Lite" database (CC BY 4.0, https://db-ip.com) for visitor locations.
# Runs as a one-shot container before Alloy; refreshes when the copy is older than 30 days.
set -eu
DB=/geoip/dbip-city-lite.mmdb
if [ -s "$DB" ] && [ -z "$(find "$DB" -mtime +30)" ]; then echo "geoip db fresh"; exit 0; fi
for m in "$(date -u +%Y-%m)" "$(date -u -d "$(date -u +%Y-%m-15) -1 month" +%Y-%m 2>/dev/null || date -u +%Y-%m)"; do
  if wget -q -O /tmp/db.gz "https://download.db-ip.com/free/dbip-city-lite-$m.mmdb.gz"; then
    gunzip -c /tmp/db.gz > "$DB.tmp" && mv "$DB.tmp" "$DB" && echo "geoip db $m ready" && exit 0
  fi
done
echo "geoip download failed; visitor locations stay empty until the next start" >&2
[ -s "$DB" ] || : > "$DB"   # empty placeholder so Alloy still starts
