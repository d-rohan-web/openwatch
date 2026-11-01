"""Collector: runs every feed, archives what it gets, publishes live state to Redis.

python -m apps.collector.main
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import os
import pkgutil
import re
import time

import redis.asyncio as aioredis
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from apps.collector import feeds as feeds_pkg
from apps.collector.feed import SECTIONS, Ctx, Feed, new_client
from packages.common import config
from packages.common.archive import Archive
from packages.common.live import EVENTS, FEEDS_KEY, dumps, health_key, live_key
from packages.common.logging import configure_logging
from packages.contracts.record import utcnow

log = logging.getLogger("collector")

FETCHES = Counter("openwatch_fetch_total", "Feed fetches", ["feed", "result"])
RECORDS = Counter("openwatch_records_total", "Records received", ["feed"])
STORED = Counter("openwatch_records_stored_total", "Records written to the archive", ["feed"])
LIVE = Gauge("openwatch_live_records", "Records in live state", ["feed"])
LAST_OK = Gauge("openwatch_last_ok_timestamp", "Unix time of the last successful fetch", ["feed"])
# live records by severity: the situation over time (Grafana "Situation" dashboard)
LIVE_SEV = Gauge("openwatch_live_severity", "Live records by severity", ["feed", "severity"])
FAILS = Gauge("openwatch_feed_failing", "1 while a feed's last fetch failed", ["feed"])
FETCH_SECONDS = Histogram("openwatch_fetch_seconds", "Time to fetch and parse one poll of a feed", ["feed"],
                          buckets=(0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300))
ARCHIVE_BYTES = Gauge("openwatch_archive_bytes", "Archive size on disk", ["kind"])
ARCHIVE_FILES = Gauge("openwatch_archive_files", "Files in the archive", ["kind"])


def load_feeds() -> list[Feed]:
    out = []
    for m in pkgutil.iter_modules(feeds_pkg.__path__):
        if m.name.startswith("_"):
            continue
        f: Feed = importlib.import_module(f"{feeds_pkg.__name__}.{m.name}").FEED
        # real checks, not asserts: `python -O` would strip those
        if f.section not in SECTIONS:
            raise ValueError(f"{f.id}: section {f.section!r} not in {SECTIONS}")
        if (f.fetch is None) == (f.stream is None):
            raise ValueError(f"{f.id}: set exactly one of fetch/stream")
        out.append(f)
    ids = [f.id for f in out]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate feed ids: {ids}")
    return [f for f in out if not config.FEEDS or f.id in config.FEEDS]


def redact(msg: str, feeds: list[Feed]) -> str:
    """Error text often carries the request URL; keys must never reach logs, Redis or the UI."""
    for f in feeds:
        for name in filter(None, [f.key]):
            for part in filter(None, re.split(r"[:]", os.environ.get(name, ""))):
                if len(part) >= 6:
                    msg = msg.replace(part, "***")
    return re.sub(r"(?i)((?:api_?)?key|token|secret|password)=[^&\s'\"]+", r"\1=***", msg)



def signature(recs: list[dict]) -> int:
    """What browsers would see of a feed's records; ignores fetched_at, which every poll restamps."""
    return hash(dumps([{k: v for k, v in r.items() if k != "fetched_at"} for r in recs]))


def should_push(last: tuple[int, float] | None, sig: int, now: float, push_every: float) -> bool:
    """Send records when they changed, and not more often than push_every."""
    return last is None or (sig != last[0] and now - last[1] >= push_every)


def next_poll(every: float, fails: int) -> float:
    """Seconds until the next poll. A failing feed retries after 1, 2, 4… minutes (at most hourly), not after its
    normal interval: a weekly feed that hit a timeout on startup would otherwise sit empty for two weeks."""
    return min(60 * 2 ** (fails - 1), 3600) if fails else every

class Runner:
    def __init__(self, feeds: list[Feed], archive: Archive, r: aioredis.Redis):
        self.feeds, self.archive, self.r = feeds, archive, r
        self.state: dict[str, dict[str, dict]] = {f.id: {} for f in feeds}  # feed -> id -> record
        self.seen: dict[str, dict[str, float]] = {f.id: {} for f in feeds}  # non-snapshot: id -> monotonic seen
        self.health: dict[str, dict] = {f.id: {"state": "STARTING", "last_ok_at": None, "last_error": None,
                                               "last_error_at": None, "last_count": 0, "stored_total": 0,
                                               "fails": 0} for f in feeds}
        self.dirty: set[str] = set()
        self.pushed: dict[str, tuple[int, float]] = {}  # feed -> (signature, monotonic time) of the records last sent

    def take(self, f: Feed, records: list[dict], raw_sha: str | None) -> None:
        """Stamp, archive and fold a batch into live state."""
        now = utcnow()
        for rec in records:
            rec["feed"], rec["fetched_at"] = f.id, now
            rec.setdefault("raw_sha256", raw_sha)
        n = self.archive.append(f.id, records, f.store_all)
        STORED.labels(f.id).inc(n)
        RECORDS.labels(f.id).inc(len(records))
        self.health[f.id]["stored_total"] += n
        if f.snapshot:
            self.state[f.id] = {rec["id"]: rec for rec in records}
        else:
            t = time.monotonic()
            for rec in records:
                self.state[f.id][rec["id"]] = rec
                self.seen[f.id][rec["id"]] = t
        self.dirty.add(f.id)

    def ok(self, f: Feed, count: int) -> None:
        h = self.health[f.id]
        h.update(state="OK", last_ok_at=utcnow(), last_count=count, fails=0)
        FETCHES.labels(f.id, "ok").inc()
        LAST_OK.labels(f.id).set(time.time())
        self.dirty.add(f.id)

    def fail(self, f: Feed, e: BaseException) -> None:
        h = self.health[f.id]
        h["fails"] += 1
        # one bad poll is DEGRADED (we still show the last good data); three in a row is DOWN
        h.update(state="DOWN" if h["fails"] >= 3 else "DEGRADED", last_error=redact(f"{type(e).__name__}: {e}", self.feeds)[:500],
                 last_error_at=utcnow())
        FETCHES.labels(f.id, "error").inc()
        log.warning("feed failed", extra={"feed": f.id, "error": h["last_error"], "fails": h["fails"]})
        self.dirty.add(f.id)

    async def poll(self, f: Feed, client) -> None:
        ctx = Ctx(f, client, lambda body, ext: self.archive.save_raw(f.id, body, ext))
        while True:
            try:
                ctx.raw_sha = None
                t = time.monotonic()
                records = await f.fetch(ctx)
                FETCH_SECONDS.labels(f.id).observe(time.monotonic() - t)
                self.take(f, records, ctx.raw_sha)
                self.ok(f, len(records))
            except Exception as e:  # a broken source must never take the collector down
                self.fail(f, e)
            await asyncio.sleep(next_poll(f.every, self.health[f.id]["fails"]))

    async def streamer(self, f: Feed, client) -> None:
        ctx = Ctx(f, client, lambda body, ext: self.archive.save_raw(f.id, body, ext))

        def emit(records: list[dict]) -> None:
            self.take(f, records, None)
            self.ok(f, len(records))

        while True:
            try:
                await f.stream(ctx, emit)
                raise ConnectionError("stream ended")
            except Exception as e:
                self.fail(f, e)
            await asyncio.sleep(min(5 * 2 ** self.health[f.id]["fails"], 300))

    async def publish(self) -> None:
        """Every 2 s push changed feeds to Redis (batches high-rate feeds into one message)."""
        while True:
            await asyncio.sleep(2)
            t = time.monotonic()
            for f in self.feeds:
                if f.ttl and not f.snapshot:
                    stale = [i for i, s in self.seen[f.id].items() if t - s > f.ttl]
                    for i in stale:
                        self.state[f.id].pop(i, None)
                        self.seen[f.id].pop(i, None)
                    if stale:
                        self.dirty.add(f.id)
            dirty, self.dirty = self.dirty, set()
            if not dirty:
                continue
            pipe = self.r.pipeline()
            by_id = {f.id: f for f in self.feeds}
            for fid in dirty:
                recs = list(self.state[fid].values())
                LIVE.labels(fid).set(len(recs))
                for sev in ("info", "advisory", "warning", "critical"):
                    LIVE_SEV.labels(fid, sev).set(sum(r.get("severity") == sev for r in recs))
                FAILS.labels(fid).set(1 if self.health[fid]["state"] in ("DEGRADED", "DOWN") else 0)
                h = {**self.health[fid], "live_count": len(recs)}
                pipe.set(health_key(fid), dumps(h))
                sig = signature(recs)
                if should_push(self.pushed.get(fid), sig, t, by_id[fid].push_every):
                    self.pushed[fid] = (sig, t)
                    pipe.set(live_key(fid), dumps(recs)).publish(EVENTS, fid)
                else:  # same records (or too soon): browsers only need the new health
                    pipe.publish(EVENTS, f"{fid} health")
            try:
                await pipe.execute()
            except Exception as e:
                self.dirty |= dirty  # retry next tick
                log.warning("redis publish failed", extra={"error": str(e)})

    async def housekeeping(self) -> None:
        while True:
            try:
                n = await asyncio.to_thread(self.archive.compact)
                m = await asyncio.to_thread(self.archive.prune, config.RETENTION_DAYS, config.RAW_RETENTION_DAYS)
                for kind, (size, files) in (await asyncio.to_thread(self.archive.usage)).items():
                    ARCHIVE_BYTES.labels(kind).set(size)
                    ARCHIVE_FILES.labels(kind).set(files)
                if n or m:
                    log.info("housekeeping", extra={"compacted": n, "pruned_dirs": m})
            except Exception:
                log.exception("housekeeping failed")
            await asyncio.sleep(300)


async def main() -> None:
    configure_logging(config.LOG_LEVEL)
    feeds = load_feeds()
    r = aioredis.from_url(config.REDIS_URL)
    runner = Runner(feeds, Archive(config.DATA_DIR), r)
    metas = []
    for f in feeds:
        meta = f.meta()
        if f.key and not Ctx(f, None, None).key:
            runner.health[f.id]["state"] = "NEEDS_KEY"
        metas.append(meta)
    await r.set(FEEDS_KEY, dumps(metas))
    runner.dirty |= {f.id for f in feeds}
    start_http_server(9101)
    log.info("collector started", extra={"feeds": [f.id for f in feeds]})
    async with new_client() as client:
        tasks = [runner.publish(), runner.housekeeping()]
        for f in feeds:
            if runner.health[f.id]["state"] == "NEEDS_KEY":
                continue
            tasks.append(runner.poll(f, client) if f.fetch else runner.streamer(f, client))
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
