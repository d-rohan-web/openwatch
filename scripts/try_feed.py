"""Run one feed's fetch once against the live source and print what came back (no Redis needed).

uv run python -m scripts.try_feed <feed_id> [--all]
"""
import asyncio
import importlib
import json
import sys
import tempfile

from apps.collector.feed import Ctx, new_client
from packages.common.archive import Archive


async def main(fid: str, show_all: bool) -> None:
    feed = importlib.import_module(f"apps.collector.feeds.{fid}").FEED
    archive = Archive(tempfile.mkdtemp())
    async with new_client() as client:
        ctx = Ctx(feed, client, lambda body, ext: archive.save_raw(feed.id, body, ext))
        if feed.stream:
            got = []
            try:
                await asyncio.wait_for(feed.stream(ctx, got.extend), 30)
            except TimeoutError:
                pass
            records = got
        else:
            records = await feed.fetch(ctx)
    located = sum(r["lon"] is not None for r in records)
    print(f"{fid}: {len(records)} records, {located} located, hosts={feed.hosts}")
    for r in records if show_all else records[:3]:
        print(json.dumps(r, ensure_ascii=False, default=str)[:600])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], "--all" in sys.argv))
