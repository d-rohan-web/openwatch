"""Feed contract and the polite HTTP context feeds fetch through.

A feed is one module in apps/collector/feeds/ exposing `FEED = Feed(...)`. It either polls (`fetch`, called every
`every` seconds, returns records) or streams (`stream`, runs forever and calls `emit(records)`).
"""
from __future__ import annotations

import asyncio
import os
import ssl
import time
from dataclasses import dataclass, field
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import certifi
import httpx

from packages.common import config

SECTIONS = ("air", "sea", "space", "defence", "hazards", "infrastructure", "economy", "govt")


@dataclass
class Feed:
    id: str
    label: str
    section: str            # one of SECTIONS: where the map's layer list puts it
    homepage: str           # human page for the source
    terms: str              # licence / terms, shown in the UI and written into exports
    every: float = 300      # seconds between polls
    fetch: Callable[[Ctx], Awaitable[list[dict]]] | None = None
    stream: Callable[[Ctx, Callable[[list[dict]], None]], Awaitable[None]] | None = None
    key: str | None = None  # env var that must be set, else the feed stays off as NEEDS_KEY
    snapshot: bool = True   # each fetch is the full current set; False: merge and expire after `ttl`
    ttl: float = 0          # non-snapshot feeds: drop a live record not seen for this many seconds
    store_all: bool = False  # archive every record (moving things) instead of only changed ones
    keep_raw: bool = True   # archive raw responses (off for high-rate feeds whose raw bytes never repeat)
    hosts: list[str] = field(default_factory=list)  # outbound hosts, filled in from requests as they happen

    def meta(self) -> dict:
        return {"id": self.id, "label": self.label, "section": self.section, "homepage": self.homepage,
                "terms": self.terms, "every": self.every, "key": self.key, "streaming": self.stream is not None}


# One request at a time per host, at least this many seconds apart: we are a guest on government servers.
HOST_GAP = float(os.getenv("OPENWATCH_HOST_GAP", "1.0"))
_host_locks: dict[str, asyncio.Lock] = {}
_host_last: dict[str, float] = {}


class Ctx:
    """Handed to a feed: HTTP that archives raw bytes, and access to its key."""

    def __init__(self, feed: Feed, client: httpx.AsyncClient, save_raw: Callable[[bytes, str], str]):
        self.feed, self.client, self._save_raw = feed, client, save_raw
        self.raw_sha: str | None = None  # sha of the last response, stamped on records that don't name their own

    @property
    def key(self) -> str:
        return os.environ.get(self.feed.key or "", "")

    async def get(self, url: str, *, raw_ext: str | None = None, **kw) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        if host not in self.feed.hosts:
            self.feed.hosts.append(host)
        lock = _host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = _host_last.get(host, 0) + HOST_GAP - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await self.client.get(url, **kw)
            finally:
                _host_last[host] = time.monotonic()
        r.raise_for_status()
        if self.feed.keep_raw:
            ext = raw_ext or _ext(r.headers.get("content-type", ""))
            self.raw_sha = self._save_raw(r.content, ext)
        return r


def _ext(ctype: str) -> str:
    for k, v in (("json", "json"), ("xml", "xml"), ("rss", "xml"), ("html", "html"), ("pdf", "pdf"),
                 ("csv", "csv"), ("text", "txt")):
        if k in ctype:
            return v
    return "bin"


# certifi + intermediates some government hosts forget to send (verification stays on)
EXTRA_CA = os.path.join(os.path.dirname(__file__), "..", "..", "packages", "common", "data", "extra_ca.pem")


def new_client() -> httpx.AsyncClient:
    tls = ssl.create_default_context(cafile=certifi.where())
    tls.load_verify_locations(cafile=EXTRA_CA)
    return httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, verify=tls,
                             headers={"User-Agent": config.USER_AGENT})
