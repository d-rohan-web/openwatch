# OpenWatch — live open-data situation map of India (design)

Status: built (v0.1) · 2026-10-31 · Rohan Das · see §11 for where the build differs
Originally drafted under the working name "Drishti"; renamed to OpenWatch (India) by the owner on 2026-10-31.

## 1. Intent

A live ops-desk map of India that pulls every useful **public** live source — government, airspace, aircraft,
defence, space, ships, disasters, infrastructure — onto one screen, and **stores everything it sees** so anyone can
later export a time/area/feed slice for an investigation or a dataset.

Inspired by commercial situational-awareness tools, but this is a **fresh, independent, open-source project**. No code,
data files, names or assets come from that tool. Personal project, lives in `~/dev-workspace/openwatch`, will be
published on GitHub.

Primary user: someone watching it live (ops-desk style). Secondary: someone pulling stored data later.

## 2. Goals

1. Live map of India + surrounding region (Indian Ocean / NAVAREA VIII, neighbours), updating without reload.
2. One module per source; adding a source = one Python file + one frontend layer file.
3. Every record ingested is stored append-only with when it was fetched, where it came from, and the original bytes.
4. Export: pick time window + area (bbox or drawn polygon) + feeds → download GeoJSON / CSV / Parquet bundle with a
   manifest (sources, licences, record counts, sha256).
5. Feed health visible at all times (last OK, last error, records/min, state).
6. Runs with `docker compose up` on a laptop; later hosted on a server unchanged.
7. Works with zero API keys (keyed sources just show "needs key" and stay off).

## 3. Non-goals / anti-goals

- **No ontology** — no typed object graph, no versioned entities, no lineage model. Flat records only.
- **No drones** (no fleet, no MAVLink, no mission planning).
- **No separate road panel.** Road traffic exists only as a map layer.
- No LLM assistant, no auth system of our own, no multi-tenant (v1). Self-hosters put a reverse proxy with basic auth
  in front if they need it.
- No private / leaked / paywalled data. No circumventing logins, CAPTCHAs or IP blocks. Public pages only.
- Anti-goal: a map whose India boundary differs from the official one (see §7). That would make it unusable for
  Indian users and is a legal problem.
- Anti-goal: hammering government servers. Polite polling intervals, caching, `User-Agent` with project URL.

## 4. Sources (v1)

Access: **API** = documented feed/API · **Scrape** = public HTML/PDF/JSON without a documented API (user approved
scraping public government pages) · **Key** = free key, off until set in `.env`.

### Aviation / airspace
| Feed | Source | Access | Poll |
|---|---|---|---|
| Aircraft (ADS-B), military flag | adsb.lol `/v2/point/{lat}/{lon}/{r}` tiled over India (ODbL 1.0) | API | 10 s |
| NOTAMs (Indian FIRs VIDF/VABF/VECF/VOMF) | AAI AIM-India | Scrape | 15 min |
| NOTAMs fallback | FAA NOTAM API | Key | 15 min |
| Restricted / danger / prohibited areas | AAI eAIP ENR 5.1 (parse once per AIRAC cycle) | Scrape | daily |
| Airports | OurAirports (public domain) | static | weekly |

### Maritime / defence
| Feed | Source | Access | Poll |
|---|---|---|---|
| Ships (AIS), India EEZ + Indian Ocean bbox | aisstream.io websocket (beta, no SLA) | Key | stream |
| NAVAREA VIII nav warnings (firing/missile-test areas) | Indian Navy NHO `hydrobharat.gov.in` | Scrape | 1 h |
| Defence press releases | PIB RSS (MoD filter) | API | 10 min |
| Military aircraft | derived from ADS-B `dbFlags` | — | — |

### Space
| Feed | Source | Access | Poll |
|---|---|---|---|
| Satellites over India (ISRO + all, propagated) | CelesTrak GP (OMM JSON), `sgp4` | API | 6 h fetch, propagate live |
| Launches (ISRO + others) | Launch Library 2 (The Space Devs) | API | 1 h |
| Space weather (Kp, flares) | NOAA SWPC JSON | API | 15 min |

### Disasters / weather / earth
| Feed | Source | Access | Poll |
|---|---|---|---|
| All-agency disaster alerts (CAP, district polygons) | NDMA SACHET `cap_public_website/rss/rss_india.xml` | API | 2 min |
| IMD district warnings + nowcast | IMD public endpoints (`warnings_district_api.php`, `nowcast_district_api.php`) | Scrape | 10 min |
| Cyclone bulletins | IMD RSMC New Delhi | Scrape | 30 min |
| Earthquakes (India) | NCS `seismo.gov.in` | Scrape | 2 min |
| Earthquakes (region, cross-check) | USGS GeoJSON feed clipped to bbox | API | 2 min |
| Tsunami / high-wave / ocean state | INCOIS | Scrape | 15 min |
| River levels (~175 FF stations) | CWC `ffs.india-water.gov.in` | Scrape | 30 min |
| Fires | NASA FIRMS (VIIRS/MODIS, India) | Key | 15 min |
| Air quality (CPCB stations) | data.gov.in real-time AQI resource | Key | 1 h |
| Landslide alerts | GSI Bhusanket | Scrape | 1 h |

### Infrastructure / government
| Feed | Source | Access | Poll |
|---|---|---|---|
| Power demand / frequency | Grid-India / MERIT dashboard | Scrape | 5 min |
| Internet outages (national + state) | IODA | API | 10 min |
| Cyber advisories | CERT-In advisories | Scrape | 1 h |
| Govt press (all ministries) | PIB RSS | API | 10 min |
| News mentions, geolocated | GDELT 2.0 (India filter) | API | 15 min |
| Road traffic (layer only, no panel) | TomTom traffic flow tiles | Key | tiles |

The builder may add more public Indian sources that fit the same shape. Each source carries `label`, `homepage`,
`licence/terms` text and its outbound host(s), shown in the UI and written into exports.

## 5. Architecture

```
docker compose
 ├─ openwatch   (one Python 3.12 container)
 │    ├─ collectors   asyncio tasks, one module per feed (httpx, selectolax/lxml, pdfplumber for PDFs)
 │    ├─ store        append-only writer (below)
 │    ├─ live         in-memory latest-state per feed → SSE /api/stream
 │    └─ api          FastAPI: /api/feeds, /api/live, /api/stream, /api/query, /api/export; serves built SPA
 └─ (optional) caddy  TLS + basic auth when hosted
```

One process, no broker, no database server (my call: fewest moving parts; DuckDB + Parquet handle export queries).
If one container stops scaling, split collectors from api — they share only the data volume.

### Record (flat, the only shape)
```
feed        str      e.g. "adsb", "sachet", "navarea8"
id          str      stable per-feed id (icao24, CAP identifier, warning no.)
observed_at ts       source's own time (or fetched_at if none)
fetched_at  ts       when we got it
lon, lat    float?   representative point
geometry    geojson? polygon/line when the source has one
kind        str      short type within the feed ("aircraft", "warning", "quake", …)
severity    str?     info|advisory|warning|critical when the source says
title       str
attrs       json     everything else from the source, untouched
raw_sha256  str      points at the raw blob it came from
```

### Store
- `data/records/feed=<f>/date=<YYYY-MM-DD>/hour=<HH>.parquet` — records, written in batches (flush every ~30 s or
  N rows; current hour kept as a JSONL spool and compacted to Parquet when the hour closes).
- `data/raw/<feed>/<YYYY-MM-DD>/<sha256>.<ext>` (zstd) — original response bytes, deduped by hash.
- Fast-moving feeds (ADS-B, AIS) store every position; slow feeds store a record only when content changes
  (hash of `attrs+geometry+severity`).
- Retention per feed in `config.yaml` (default: keep forever; raw blobs default 90 days). Rough size guess: ADS-B over
  India ≈ a few hundred MB/day as Parquet.
- On restart, live state is rebuilt from the last few hours of records.

### Export
`POST /api/export {from, to, bbox|polygon, feeds[], format: geojson|csv|parquet, include_raw: bool}` → DuckDB query
over Parquet → zip with data files + `manifest.json` (query, generated_at, per-feed counts, source licence/terms,
sha256 of each file). Large exports stream; no job queue in v1.
CLI equivalent (`python -m openwatch export …`) for people working on the box.

## 6. Frontend

React + Vite + MapLibre GL + deck.gl. Static build served by FastAPI.

- **Map** fills most of the screen. Layer registry: one file per layer (`layers/<feed>.tsx`) declaring id, label,
  section (Air · Sea · Space · Hazards · Infrastructure · Govt/News), style, detail card. Keyed-but-unset layers show
  "needs key".
- **Panels** (dockable side column): Feed health · Alerts (SACHET/IMD/NCS/NAVAREA/NOTAM, newest first, severity
  colour) · Selected record detail (all attrs + source link + raw download) · Export.
- Live updates via SSE; aircraft/ships interpolated between updates.
- Time range filter (1h/6h/24h/7d) on what's drawn. Replay from the store is a nice-to-have, not v1.
- Each layer's attribution shown on the map while it's on (ODbL etc. require it).
- 2D map in v1. 3D globe not needed.

## 7. Constraints

- **Boundary:** draw India's official boundary per Survey of India; suppress basemap admin borders for India. Builder
  picks the source (e.g. a SOI-aligned community dataset with a compatible licence) and documents it.
- Basemap: free and self-hostable (e.g. Protomaps PMTiles or OpenFreeMap). No paid basemap required.
- All dependencies OSI-licensed. Project licence: MIT (my call; change if you prefer Apache-2.0).
- Licence of stored data follows its source; exports carry the terms. ODbL (adsb.lol) attribution + share-alike
  noted in README.
- Polite scraping: per-host rate limit, backoff on errors, honour `robots.txt` where present, identify the project in
  `User-Agent`. A scraper that breaks marks its feed DEGRADED; it never takes the app down.
- `.env` only for keys and host settings; everything else in `config.yaml`.

## 8. Decided by the user

- Live ops-desk use first; stored data for later export.
- Docker Compose; laptop first, hosted later.
- All live sources; scraping public government pages without APIs is fine; add any useful government sources.
- No ontology, no drones, no road panel (road function as a layer if possible).
- Personal open-source project under `~/dev-workspace`, independent of company code.

## 9. My calls (check these)

Name · single Python container, Parquet+DuckDB instead of Postgres · TomTom as optional keyed road layer ·
keep-forever default retention · MIT licence · no auth in app · 2D map only · replay deferred.

## 10. Left to the builder

Exact parsers per scraper, tiling of ADS-B queries, Parquet schema details, UI styling, test approach (one fixture
test per parser with a saved sample response).

## 11. As built (differences from this draft)

- Services follow an SOS-style layout at the owner's request: `apps/{collector,api,frontend}`, `packages/`,
  `infrastructure/` (nginx TLS, certs-init, Prometheus/Loki/Alloy/Grafana), JSON logs. Collector and api are separate
  containers sharing the archive volume, with Redis for live state and pub/sub.
- Settings live in env (`.env`) only; there is no config.yaml.
- The UI was redesigned to float over a full-screen map: a category dock instead of a sidebar, an intel panel, a KPI
  strip and ⌘K search. The India view is locked to India + ~200 km of sea.
- A Global scope (`OPENWATCH_SCOPE=global`) widens the region-filtered feeds.
- Export can window on receive time (default) or source time.
- Sources skipped (blocked or not public): PIB, AAI NOTAMs (FAA API instead), GSI landslide, live grid frequency.
  See docs/DATA_SOURCES.md.
