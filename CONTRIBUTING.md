# Contributing to OpenWatch India

Thanks for helping. OpenWatch is a live, open-source situational-awareness map of India built only on public data.

## Ground rules

- **Public sources only.** Never work around logins, CAPTCHAs, IP allow-lists, bot walls (403s) or TLS verification,
  and never spoof a browser User-Agent. If a source blocks automated access, leave it out and note it in
  `docs/DATA_SOURCES.md`.
- **Licences matter.** Every feed states its source's licence or terms in `terms`. Don't add data you can't redistribute.
- **India's official boundary.** Maps use the Survey of India outline (`apps/frontend/public/geo/india.geojson`).
  De-facto lines stay optional and clearly labelled.
- **Sensitive locations.** Only publicly documented sites (e.g. Wikidata/Wikipedia). No leaked, classified or
  "not for public use" material.
- **No secrets in the repo.** Keys live in `.env` (gitignored). Error text is redacted before it is logged.

## Development

```bash
uv sync                                   # Python 3.12
cd apps/frontend && npm ci && cd ../..
docker compose up -d --build              # full stack → https://localhost:39443
uv run pytest -q                          # backend tests
cd apps/frontend && npm test && npx tsc --noEmit
```

## Adding a data source

1. Create `apps/collector/feeds/<id>.py` exposing `FEED = Feed(...)`. Keep parsing in a pure function.
2. Save a small, trimmed real sample in `tests/fixtures/` and add `tests/feeds/test_<id>.py`.
3. Check it live: `uv run python -m scripts.try_feed <id>`.
4. Regenerate the sources table: `uv run python -m scripts.sources` → `docs/DATA_SOURCES.md`.
5. Poll politely: minutes, not seconds, for government servers.

## Pull requests

- Branch from `main`, keep PRs focused, and use a [Conventional Commits](https://www.conventionalcommits.org/) title
  (`feat: …`, `fix: …`, `docs: …`). A bot checks it.
- CI must pass (backend tests, frontend types/tests/build, Docker build). A maintainer review is required to merge.
- UI changes: include a screenshot.

## Reporting issues

Use the issue templates. For security problems, see [SECURITY.md](SECURITY.md); please don't open a public issue.
