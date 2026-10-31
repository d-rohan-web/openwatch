<!-- PRs without a linked issue are closed by the PR policy check. Open an issue first and agree the approach. -->

Closes #

## What & why

<!-- What this changes and the problem it solves (one or two sentences). -->

## Approach

<!-- How you implemented it, and anything you considered and rejected. Should match what was agreed on the issue. -->

## Screenshots

<!-- UI changes only. -->

## Checklist

- [ ] No paid source: data is free and public (a free API key is OK if explained above)
- [ ] Source is reached honestly: no login/CAPTCHA/bot-wall bypass, no spoofed browser User-Agent, TLS on
- [ ] Follows the project structure (one feed = one file in `apps/collector/feeds/`, parsing in a pure function)
- [ ] Tests added/updated: `uv run pytest -q` and `cd apps/frontend && npm test` pass
- [ ] Lint clean: `uv run ruff check .` and `npx tsc --noEmit`
- [ ] No secrets, keys or personal data in the diff
- [ ] Docs updated (`docs/DATA_SOURCES.md` regenerated for feed changes)
