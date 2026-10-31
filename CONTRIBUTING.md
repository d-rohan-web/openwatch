# Contributing to OpenWatch India

Thanks for helping. OpenWatch is a live, open-source situational-awareness map of India built only on public data.

## Purpose

OpenWatch is for **study, research and general public awareness**. It isn't affiliated with or built for any
military, defence or government body, and contributions aimed at military or operational use won't be accepted.
See [NOTICE.md](NOTICE.md).

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

## How to contribute: issue first, then a pull request

1. **Open a proposal issue** (template "Proposal") describing the **problem**, your **proposed solution** and your
   **approach** (files/modules you'll change, alternatives considered, the data source and its licence).
2. **Wait for agreement.** A maintainer discusses it and labels it `approved`. This saves you from writing code that
   can't be merged.
3. **Fork, branch, and push to your fork.** You can't push to this repo directly; work on your own fork:
   ```bash
   # on GitHub: click "Fork" on d-rohan-web/openwatch
   git clone https://github.com/<your-username>/openwatch.git && cd openwatch
   git remote add upstream https://github.com/d-rohan-web/openwatch.git
   git checkout -b feat/<short-name>             # one branch per issue
   # …make your changes, run the checks below…
   git commit -m "feat: add <source> feed"        # Conventional Commits
   git push -u origin feat/<short-name>
   ```
   Keep your branch current with `git fetch upstream && git rebase upstream/main` (then `git push --force-with-lease`).
4. **Open a pull request** from your fork's branch to `d-rohan-web/openwatch:main` that links the issue
   (`Closes #12`) and fills every section of the template
   (What & why, Approach, Checklist). The *PR policy* check rejects PRs without a linked issue or the template.
5. **Keep to the project's structure and quality**:
   - one data source = one file in `apps/collector/feeds/`, parsing in a pure function, a fixture test;
   - shared helpers live in `packages/`, the record shape stays flat (`packages/contracts/record.py`);
   - match the surrounding code style; `uv run ruff check .`, `uv run pytest -q`, `npx tsc --noEmit` and `npm test` pass;
   - small, focused PRs with a [Conventional Commits](https://www.conventionalcommits.org/) title (`feat: …`, `fix: …`).
6. **Review**: the review bot runs first (lint, security patterns, leak scan, AI-code smells such as placeholders,
   disabled TLS, spoofed user agents, hardcoded keys), then AI reviewers leave inline comments (Claude on branches in
   this repo; GitHub withholds secrets from fork PRs, so forks get the bots and a maintainer). A maintainer reviews
   and merges once all required checks are green.

### Data source rules

- **No paid sources.** Data must be free to access. A *free* API key is acceptable only when no keyless source
  exists; explain why in the PR.
- Public data only, reached honestly (see Ground rules above).

## Reporting issues

Use the issue templates. For security problems, see [SECURITY.md](SECURITY.md); please don't open a public issue.
