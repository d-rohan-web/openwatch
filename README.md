# OpenWatch <sub>India</sub>

[![CI](https://github.com/d-rohan-web/openwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/d-rohan-web/openwatch/actions/workflows/ci.yml)
[![CodeQL](https://github.com/d-rohan-web/openwatch/actions/workflows/codeql.yml/badge.svg)](https://github.com/d-rohan-web/openwatch/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A live, open-source situational-awareness map of India.** OpenWatch<sub>India</sub> pulls every useful public
feed it can find: aircraft, airspace, maritime warnings, satellites, earthquakes, weather warnings, floods, ocean
alerts, power, internet outages, cyber advisories and news. It puts them on one map, and **archives everything it sees**
so you can later export a time/area/feed slice for an investigation or a dataset.

- **Live**: an ops-desk view that updates in real time (server-sent events), with alerts, feed health and search (⌘K).
- **Archived**: every record and the original source bytes, stored as hourly Parquet files. Nothing is overwritten.
- **Exportable** *(coming soon)*: GeoJSON / CSV / Parquet slices with a manifest (query, counts, licences, checksums).
  Built in, switched off by default (`OPENWATCH_EXPORT_ENABLED=false`) until paid access is ready.
- **India first**: the map shows India's official boundary (Survey of India) and dims everything outside it.
  Global coverage is upcoming.
- **No keys needed**: most feeds run without any key. Free keys switch on ships, fires, air quality, NOTAMs, road
  traffic and faster OpenSky polling.

> **Notice:** OpenWatch is an independent project for **study and general public awareness only**. It isn't
> affiliated with any military or government body, uses only public data, and must not be used for military,
> operational or safety-of-life purposes. See [NOTICE.md](NOTICE.md).

## Quick start

```bash
cp .env.example .env            # optional: add free API keys
docker compose up -d --build
open https://localhost:39443    # self-signed certificate on first run
```

Monitoring (Prometheus, Loki, Alloy, Grafana with a feed dashboard):

```bash
docker compose --profile monitoring up -d
open http://localhost:39300     # admin / GRAFANA_ADMIN_PASSWORD
```

Global coverage is upcoming (experimental: `OPENWATCH_SCOPE=global`).

**Deploy** to a free Google Cloud e2-micro VM with automatic HTTPS from Cloud Shell in one command: see
[docs/deploy.md](docs/deploy.md).

## What's on the map

| Group | Feeds and overlays |
|---|---|
| Air | live aircraft: adsb.fi (military flagged) + OpenSky (free account = 90 s refresh), drawn as planes that glide between reports · runways & navaids · airports & heliports · prohibited/restricted/danger areas (AAI eAIP) · NOTAMs (FAA key) |
| Sea | NAVAREA VIII navigational warnings incl. firing/missile areas (Indian Navy NHO) · ships (AIS, aisstream key) · maritime zones: territorial sea 12 nm, contiguous zone 24 nm, EEZ (Marine Regions) |
| Space | every Indian satellite + NavIC + stations (CelesTrak + SGP4), with mission, orbit class, inclination, period, apogee/perigee; satellites glide live along their orbit; click one for its pass track, minute ticks and coverage footprint; the Satellites tab groups them by mission · launches (ISRO and region) · space weather (NOAA SWPC) |
| Defence | publicly documented defence sites and land border crossings (Wikidata, CC0) · optional LoC / LAC de-facto lines (Natural Earth) |
| Hazards | NDMA SACHET all-agency CAP alerts · IMD district warnings, nowcast, cyclone bulletins · NCS + USGS earthquakes · INCOIS ocean & tsunami alerts · CWC rivers above warning · city weather (Open-Meteo) · volcanoes (Smithsonian GVP) · NASA FIRMS fires (key) · CPCB air quality (key) · rivers & canals overlay (OSM) |
| Infra | nuclear sites (Wikidata) · power demand & generation mix (MERIT) · internet outages (IODA) · highways and railways overlays (OSM) · live road traffic + incidents (TomTom key) |
| Markets | SENSEX, NIFTY 50, NIFTY BANK, India VIX · INR exchange rates · gold, silver, Brent (ticker along the bottom) |
| Govt | CERT-In advisories · GDELT conflict/protest events located in India · state boundaries |

The map also offers:

- **Borders**: India's official boundary, split by neighbour with Ministry of Home Affairs lengths, plus neighbours' own borders and labels.
- **States**: click a state to fly there and get a live summary card.
- **Less clutter**: district-level warnings (IMD, SACHET) shade their districts by severity instead of drawing dots;
  dense static layers cluster into count bubbles until you zoom in; every point type has its own icon.
- **3D**: terrain, tilt and rotate, and buildings when zoomed in.
- **Search (⌘K)**: states, districts, callsigns, airports, alerts and layers.

Every feed's source, licence and terms are in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md), and the UI shows them
under each layer's ⓘ button. Data keeps its source's licence, and exports carry those terms.

## Exporting data (coming soon)

Export is switched off by default. With `OPENWATCH_EXPORT_ENABLED=true` (self-hosters):

From the UI: **Export** tab → pick feeds, a window and optionally the current map view → zip.

From the API:

```bash
curl -k -X POST https://localhost:39443/api/export -H 'content-type: application/json' \
  -d '{"feeds":["aircraft","navarea8"],"start":"2026-10-30T00:00:00Z","end":"2026-10-31T00:00:00Z",
       "format":"parquet","bbox":[72,18,74,20],"include_raw":true}' -o slice.zip
```

The window applies to when OpenWatch **received** each record (`time_field: "fetched"`, the default) or to when the
source says it **happened** (`"observed"`). You can also query the archive directly, since it's plain Parquet:

```sql
-- duckdb, inside the archive volume
SELECT * FROM read_parquet('records/feed=aircraft/date=2026-10-30/*.parquet') WHERE attrs->>'military' = 'true';
```

API docs: `https://localhost:39443/api/docs`.

## Layout

```
apps/
  collector/        polls/streams every feed → archive + Redis live state   (feeds/: one file per source)
  api/              FastAPI: live, SSE stream, history, records, export, raw, traffic tiles
  frontend/         React + MapLibre UI (static, served by nginx)
packages/
  common/           archive (Parquet/DuckDB), JSON logging, config, geo helpers + data
  contracts/        the one flat record shape
infrastructure/     caddy (automatic HTTPS, compression, SSE), monitoring (prometheus, loki, alloy, grafana)
scripts/            try_feed.py (run one feed once), build_*.py (geo files), deploy/ (Google Cloud), ci/, github/
tests/              archive, geo, one fixture test per feed
docs/               architecture, data sources, design spec
```

## Adding a feed

1. Write `apps/collector/feeds/<id>.py` exposing `FEED = Feed(...)` with an async `fetch(ctx)` that returns
   `record(...)`s (see `usgs_quakes.py` for the smallest example).
2. Run `uv run python -m scripts.try_feed <id>` to check it against the live source.
3. Add `tests/feeds/test_<id>.py` using a small saved sample in `tests/fixtures/`.

The UI picks the feed up automatically under its `section`.

## Development

```bash
uv sync                                   # Python 3.12
docker run -d -p 36379:6379 redis:7-alpine
REDIS_URL=redis://localhost:36379/0 uv run python -m apps.collector.main
REDIS_URL=redis://localhost:36379/0 uv run uvicorn apps.api.main:app --port 8000
cd apps/frontend && npm i && npm run dev  # http://localhost:5173
uv run pytest -q && (cd apps/frontend && npm test)
```

## Being a good guest

OpenWatch reads public pages and APIs only. It identifies itself in its `User-Agent`, makes one request at a time per
host with gaps between them, backs off when a source fails, and never works around logins, CAPTCHAs, IP allow-lists
or blocks. A source that blocks it is left out. Sources that publish nothing machine-readable, or label their
material "not for public use", are not ingested.

## Privacy

The app sets no cookies and uses no third-party analytics or trackers. The server keeps a standard web access log
(time, page, browser, referrer, IP address) for up to 90 days for operations and visitor counts; IPs are anonymised
in the stats report. Map tiles load from OpenFreeMap, which sees your IP like any website.

## Contributing

Contributions are welcome, especially new public Indian data sources. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately ([SECURITY.md](SECURITY.md)).

## Licence

Code: MIT. Data: each source's own terms (see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)). Boundary and district
geometry: [datameet/maps](https://github.com/datameet/maps) (CC0 / CC BY 4.0). Basemap: © OpenStreetMap contributors,
OpenMapTiles, OpenFreeMap.
