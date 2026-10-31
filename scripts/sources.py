"""Print docs/DATA_SOURCES.md's feed table from the FEED definitions: uv run python -m scripts.sources"""
from apps.collector.main import load_feeds

print("| Feed | Section | Source | Key | Poll | Terms |\n|---|---|---|---|---|---|")
for f in sorted(load_feeds(), key=lambda f: (f.section, f.id)):
    poll = "stream" if f.stream else (f"{int(f.every // 60)} min" if f.every >= 60 else f"{int(f.every)} s")
    print(f"| `{f.id}` {f.label} | {f.section} | {f.homepage} | {('`' + f.key + '`') if f.key else '—'} | {poll} | {f.terms} |")
