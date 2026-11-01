# Architecture

## 1. Services (docker compose)

| Service | Role | Port |
|---|---|---|
| `caddy` | automatic HTTPS (Let's Encrypt for a public name, internal CA on localhost), zstd/gzip, CSP and security headers; routes `/ui` → bff (SSE flushed immediately), `/` → frontend. `/api` is not served publicly unless `OPENWATCH_PUBLIC_API=true` | 39443 / 39080 (443/80 on a server) |
| `frontend` | built React + MapLibre SPA, static (nginx: hashed assets cached a year, `index.html` revalidated) | — |
| `bff` | backend for frontend: the only API the browser reaches (`/ui/*`), an allow-list of what the UI uses; calls `api` on the compose network and hides upstream errors | — |
| `api` | core FastAPI (private): live state, SSE stream, history, records, export, raw bytes, TomTom tile proxy, `/metrics` | — |
| `collector` | runs every feed; writes the archive; publishes live state + health to Redis; `/metrics` on 9101 | — |
| `redis` | live state and pub/sub only (no persistence: the archive is the record) | — |
| `prometheus`, `loki`, `alloy`, `grafana` | `monitoring` profile: metrics, JSON logs, feed dashboard | 39300 (grafana) |

Volumes: `archive` (the dataset; the collector writes it, the api mounts it read-only), `caddy_data` (certificates), plus one each for
the monitoring stores.

```
 sources ──HTTP/WS──▶ collector ──append──▶ archive volume (JSONL → hourly Parquet, raw/*.gz)
                         │                         ▲
                         └─SET/PUBLISH─▶ redis ─SUB─┤
                                                   api ◀── bff ◀── caddy ◀── browser (/ui: SSE + REST)
```

## 2. The record

One flat shape for everything, with no ontology (`packages/contracts/record.py`):

`feed, id, observed_at, fetched_at, lon, lat, geometry (GeoJSON), kind, severity, title, attrs (source fields), raw_sha256`

- `id` is stable within a feed (ICAO hex, CAP identifier, warning number…). History is just every stored row for
  that `(feed, id)`.
- `observed_at` is the source's time. `fetched_at` is when the collector got the record.
- `severity` (info / advisory / warning / critical) is set only where the source implies one.
- `raw_sha256` points at the original response bytes the record came from.

## 3. Archive (`packages/common/archive.py`)

```
records/feed=<f>/date=<YYYY-MM-DD>/hour=<HH>.jsonl     open hour, appended
records/feed=<f>/date=<YYYY-MM-DD>/hour=<HH>.parquet   closed hours (zstd), compacted every 5 min
raw/<feed>/<YYYY-MM-DD>/<sha256>.<ext>.gz              original bytes, deduped by hash
```

- **Change-only storage**: slow feeds store a record only when its content changes. Moving things
  (`store_all=True`: aircraft, ships) store every position. Change tracking lives in memory, so after a restart
  each id is stored once more.
- **Retention**: `OPENWATCH_RETENTION_DAYS` for records (0 = forever) and `OPENWATCH_RAW_RETENTION_DAYS` for raw bytes
  (default 90). Whole days are deleted.
- **Reads**: DuckDB over the Parquet files plus the open JSONL. `query()` returns SQL, which export runs as `COPY`
  (CSV/Parquet) or streams (GeoJSON).

## 4. Collector (`apps/collector`)

- A feed is a module with `FEED = Feed(...)`. It either polls (`fetch(ctx) → records`, every `every` seconds) or
  streams (`stream(ctx, emit)`, used for AIS websockets).
- `snapshot=True`: each fetch is the full current set. `snapshot=False` + `ttl`: records are merged, and a record
  drops out of live state when it hasn't been seen for `ttl` seconds.
- **Politeness** (`Ctx.get`): one request at a time per host with a minimum gap (`OPENWATCH_HOST_GAP`, default 1 s),
  an honest User-Agent, and backoff up to 8× while a feed fails.
- **Health**: one failure makes a feed DEGRADED (its last good data stays on the map); three in a row make it DOWN.
  NEEDS_KEY feeds don't run. Error text is scrubbed of keys before it reaches logs, Redis or the UI.
- **Scope**: `OPENWATCH_SCOPE=india` keeps region-filtered feeds to India + neighbours + Indian Ocean. `global` widens
  aircraft (OpenSky worldwide + global military), ships, quakes, satellites, launches and news.
- **TLS**: certifi plus `packages/common/data/extra_ca.pem`, for government hosts that don't send their
  intermediate certificate. Verification stays on.

## 5. API

The browser only talks to the **backend for frontend** (`apps/bff/main.py`). It calls the core API over the compose
network, passes 4xx details through (they're meant for users) and turns upstream failures into a plain 502.

| BFF (`/ui`, public) | Core API |
|---|---|
| `GET /ui/bootstrap` | `/api/config` + `/api/feeds` + `/api/live` in one response: the first frame |
| `GET /ui/stream` | `/api/stream`, relayed as it arrives |
| `GET /ui/feeds` | `/api/feeds` (health refresh) |
| `GET /ui/window/{feed}`, `/ui/history/{feed}/{id}`, `/ui/raw/{feed}/{sha}` | same paths under `/api` |
| `POST /ui/export`, `GET /ui/tiles/traffic/{z}/{x}/{y}.png` | same paths under `/api` |

The core API (`apps/api/main.py`, private; public only with `OPENWATCH_PUBLIC_API=true`):

| Endpoint | |
|---|---|
| `GET /api/feeds` | feed metadata + health |
| `GET /api/live` | current records of all feeds |
| `GET /api/stream` | SSE: `feed` event `{feed, records, health}` whenever a feed changes (batched every 2 s) |
| `GET /api/history/{feed}/{id}?hours=` | every stored version of one record (an aircraft's track, an alert's updates) |
| `GET /api/records?feed=&start=&end=&bbox=&time_field=` | archive search |
| `POST /api/export` | zip: `data/<feed>.<fmt>`, `manifest.json`, `README.txt`, optional `raw/` |
| `GET /api/raw/{feed}/{sha}` | original response bytes |
| `GET /api/tiles/traffic/{z}/{x}/{y}.png` | TomTom flow tiles, with the key kept on the server |

Feed ids are checked against the registered list before they reach a file path.

## 6. Frontend (`apps/frontend`)

The map fills the screen; the controls float over it:

- **Top bar**: India | Global switch, ⌘K search, live state, feed health, IST/UTC clock.
- **Layer dock**: one chip per category with a live count, each opening a card with per-layer switches, health and
  source info. "Views" holds presets (Defence, Disaster, Aviation, Maritime, Space).
- **Intel panel**: alerts with severity filters and record detail, plus Feeds and Export tabs.
- **KPI strip**: aircraft airborne, military, ships, satellites overhead, quakes in the last 24 h, weather warnings.

**India scope** locks panning to the region, dims everything outside the official outline, and hides records outside
India + ~200 km of sea (`public/geo/scope.geojson`). The basemap's own country borders are hidden.

## 7. Logging & monitoring

- Every service logs one JSON object per line to stdout, with `extra=` fields such as `feed` and `error`.
- Alloy ships the logs to Loki, labelled with `service`, `level`, `logger` and `feed`.
- Prometheus scrapes `collector:9101` and `api:8000/metrics`. Collector metrics: `openwatch_fetch_total{feed,result}`,
  `openwatch_records_total`, `openwatch_records_stored_total`, `openwatch_live_records` and `openwatch_last_ok_timestamp`.
- The Grafana dashboard "OpenWatch feeds" is provisioned from `infrastructure/monitoring/grafana/dashboards/feeds.json`.
