# CLAUDE.md

OpenWatch: an open-source, live situational-awareness map of India. Collectors pull public feeds, everything is
archived as Parquet, a FastAPI service streams live state and exports slices, and a React + MapLibre UI displays it.
Read `README.md` and `docs/architecture.md` first.

## Commands

```bash
docker compose up -d --build                       # full stack → https://localhost:39443
docker compose --profile monitoring up -d          # + grafana on :39300
docker compose logs -f collector                   # JSON logs
uv run pytest -q                                   # Python tests (archive, geo, one per feed)
cd apps/frontend && npm test && npx tsc --noEmit   # UI tests + types
uv run python -m scripts.try_feed <feed_id>        # run one feed once against the live source
uv run python -m scripts.sources                   # regenerate the docs/DATA_SOURCES.md table
```

## Rules

- **Feeds** are one file each in `apps/collector/feeds/`. They return `record(...)` only, keep parsing in a pure
  function with a fixture test, and fill `terms` honestly.
- **Politeness**: public sources only. Never work around 403s, CAPTCHAs, logins, IP allow-lists or TLS verification,
  and never spoof a browser User-Agent. If a source blocks us, leave it out and note it in `docs/DATA_SOURCES.md`.
- **Keys** come from env (`.env`) only, never from the frontend. Error text is redacted in `apps/collector/main.py`.
- **Boundary**: draw India's official outline (`public/geo/india.geojson`, from datameet `india-composite`) and keep
  the basemap's borders hidden.
- **Logging**: JSON via `packages/common/logging.py`; put context in `extra=`.
- **No ontology**: records stay flat. Don't add typed object graphs; put source fields in `attrs`.
- **Independence**: this is an independent open-source project. Don't copy code, data or names from other proprietary
  codebases.

## Reviewing pull requests

When reviewing a PR, focus on real defects, not style:
- bugs and hallucinated APIs or imports; asserts used for validation; swallowed exceptions outside the collector
- leaks: keys or tokens in code, URLs or log messages; personal data
- policy: paid or keyed sources without justification; bypassing logins, CAPTCHAs, bot walls, IP allow-lists or TLS;
  spoofed browser User-Agents; military or targeting use cases (see NOTICE.md)
- structure: one feed per file, parsing in a pure function with a fixture test, output only via `record()`
