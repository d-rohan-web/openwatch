# Security policy

## Reporting a vulnerability

Please **don't** open a public issue. Use GitHub's private reporting:
**Security → Report a vulnerability** on this repository. You'll get a response within a few days.

Include what you found, how to reproduce it, and the impact. Please give us reasonable time to fix it before
disclosing.

## Scope

- The OpenWatch code in this repository (collector, API, frontend, infrastructure configs).
- Leaks of API keys or credentials through logs, the UI or exports.

Issues in the upstream data sources themselves should go to their owners. We're happy to help route a report.

## Self-hosting notes

- Keep `.env` out of version control; it holds your API keys.
- For a private deployment, add Caddy basic auth (see docs/deploy.md) or another access layer.
- Bulk export is off by default (`OPENWATCH_EXPORT_ENABLED=false`).
