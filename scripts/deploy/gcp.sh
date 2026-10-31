#!/usr/bin/env bash
# Deploy OpenWatch to a Google Cloud always-free e2-micro VM (us-central1) with automatic HTTPS on <ip>.sslip.io.
#   PROJECT=my-project bash scripts/deploy/gcp.sh
# Needs: gcloud (logged in), a project with billing enabled. Re-running is safe.
# Cost: the e2-micro VM and its 30 GB standard disk are in the free tier; the public IPv4 address is billed by Google
# (~US$3.6/month). A US$5 budget alert is created so nothing surprises you.
set -euo pipefail
PROJECT="${PROJECT:?set PROJECT=<your gcp project id>}"
REGION="${REGION:-us-central1}"; ZONE="${ZONE:-$REGION-a}"; NAME="${NAME:-openwatch}"
here="$(cd "$(dirname "$0")" && pwd)"
g() { gcloud --project "$PROJECT" --quiet "$@"; }

echo "→ APIs"
g services enable compute.googleapis.com billingbudgets.googleapis.com >/dev/null

echo "→ static IP (same price as an ephemeral one, but survives restarts so the site name never changes)"
g compute addresses describe "$NAME-ip" --region "$REGION" >/dev/null 2>&1 || g compute addresses create "$NAME-ip" --region "$REGION"
IP=$(g compute addresses describe "$NAME-ip" --region "$REGION" --format 'value(address)')
SITE="${SITE:-${IP//./-}.sslip.io}"

echo "→ firewall: web only (SSH stays on Google's default rule)"
g compute firewall-rules describe "$NAME-web" >/dev/null 2>&1 || \
  g compute firewall-rules create "$NAME-web" --allow tcp:80,tcp:443,udp:443 --target-tags "$NAME-web" --description "OpenWatch HTTP/HTTPS"

echo "→ VM"
if ! g compute instances describe "$NAME" --zone "$ZONE" >/dev/null 2>&1; then
  g compute instances create "$NAME" --zone "$ZONE" --machine-type e2-micro \
    --image-family debian-12 --image-project debian-cloud --boot-disk-size 30GB --boot-disk-type pd-standard \
    --address "$IP" --tags "$NAME-web" \
    --metadata "openwatch-site=$SITE" --metadata-from-file "startup-script=$here/vm-setup.sh"
else
  g compute instances add-metadata "$NAME" --zone "$ZONE" --metadata "openwatch-site=$SITE" --metadata-from-file "startup-script=$here/vm-setup.sh"
  g compute ssh "$NAME" --zone "$ZONE" --command "sudo google_metadata_script_runner startup"
fi

echo "→ US\$5 budget alert (50% / 90% / 100%)"
BA=$(gcloud billing projects describe "$PROJECT" --format 'value(billingAccountName)' | sed 's#billingAccounts/##')
if [ -n "$BA" ] && ! gcloud billing budgets list --billing-account "$BA" --format 'value(displayName)' 2>/dev/null | grep -qx "$NAME"; then
  gcloud billing budgets create --billing-account "$BA" --display-name "$NAME" --budget-amount 5USD \
    --filter-projects "projects/$PROJECT" --threshold-rule percent=0.5 --threshold-rule percent=0.9 --threshold-rule percent=1.0 || \
    echo "  (couldn't create the budget; add one in Billing → Budgets & alerts)"
fi

echo
echo "✓ https://$SITE  (first boot takes ~3–5 min: Docker install, image pull, certificate)"
echo "  logs:  gcloud compute ssh $NAME --zone $ZONE --project $PROJECT --command 'cd /opt/openwatch && sudo docker compose logs -f'"
