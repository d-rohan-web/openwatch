# Deploying OpenWatch

The stack is Docker Compose. Servers pull prebuilt images from GHCR (`ghcr.io/d-rohan-web/openwatch-{api,collector,frontend}`,
published by `.github/workflows/release.yml` on every merge to `main`) and Caddy handles HTTPS automatically.

## Google Cloud (always-free e2-micro), from Cloud Shell

1. Open Cloud Shell (console.cloud.google.com → `>_`). It's already logged in.
2. Run:
   ```bash
   gcloud projects list                                   # pick your project id
   git clone https://github.com/d-rohan-web/openwatch.git && cd openwatch
   PROJECT=<your-project-id> bash scripts/deploy/gcp.sh
   ```
3. Open the printed `https://<ip>.sslip.io` after 3–5 minutes (first boot installs Docker, pulls images and gets a
   Let's Encrypt certificate).

What the script creates (all named `openwatch*`, re-running is safe):

| Resource | Notes |
|---|---|
| e2-micro VM, us-central1-a, Debian 12, 30 GB standard disk | free tier (1 per billing account, US regions only) |
| static external IPv4 | billed by Google, about US$3.6/month; keeps the site name stable |
| firewall rule `openwatch-web` | TCP 80/443, UDP 443 to the VM only |
| budget `openwatch` | US$5 with alerts at 50/90/100% |

The VM's startup script (`scripts/deploy/vm-setup.sh`) installs Docker, adds 2 GB swap, clones the repo to
`/opt/openwatch`, writes `.env`, starts the stack and installs a daily update (pull newest images at 04:00 IST).

Useful commands (Cloud Shell):

```bash
gcloud compute ssh openwatch --zone us-central1-a --command 'cd /opt/openwatch && sudo docker compose ps'
gcloud compute ssh openwatch --zone us-central1-a --command 'cd /opt/openwatch && sudo docker compose logs -f collector'
gcloud compute ssh openwatch --zone us-central1-a      # then: sudo nano /opt/openwatch/.env  (API keys), sudo docker compose up -d
```

Visitor report (HTML, built from the server's own access log: unique visitors, pages, referrers, countries,
browsers; IPs anonymised, nothing sent to third parties; downloads to your browser from Cloud Shell):

```bash
PROJECT=<your-project-id> bash scripts/deploy/stats.sh           # everything kept (up to 90 days)
PROJECT=<your-project-id> DAYS=7 bash scripts/deploy/stats.sh    # last 7 days
```
The report is a snapshot: run it again for newer days. The access log lives on the `caddy_data` volume
(`/data/access.log`, rotated at 20 MB, kept 90 days), so it survives restarts and updates.

Remove everything: `gcloud compute instances delete openwatch --zone us-central1-a && gcloud compute addresses delete openwatch-ip --region us-central1 && gcloud compute firewall-rules delete openwatch-web`.

### Free-tier notes

- Egress: 1 GB/month free from North America; JSON responses are compressed, but every open browser streams live
  updates (mostly aircraft, roughly 150–200 MB/day per viewer). A few viewers stay cheap; check Billing → Reports.
- Keys: add them to `/opt/openwatch/.env` on the VM (never commit them).

## Any other Linux server

```bash
git clone https://github.com/d-rohan-web/openwatch.git && cd openwatch && cp .env.example .env
# .env: OPENWATCH_SITE=<your-domain or a-b-c-d.sslip.io>, OPENWATCH_HTTPS_PORT=443, OPENWATCH_HTTP_PORT=80
docker compose pull && docker compose up -d --no-build
```
Ports 80 and 443 must be reachable for the certificate.

## Optional: password protection

Create `infrastructure/caddy/extra-auth.caddy` and mount it at `/etc/caddy/extra-auth.caddy` (it's picked up by the
`import /etc/caddy/extra*.caddy` line):
```
basic_auth {
	viewer <hash from: docker run --rm caddy:2.10-alpine caddy hash-password --plaintext 'your-password'>
}
```
