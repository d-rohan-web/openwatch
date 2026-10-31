"""API: live state + SSE from Redis, history and export from the archive.

uvicorn apps.api.main:app
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timedelta, UTC
from typing import Literal

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from packages.common import config
from packages.common.archive import Archive
from packages.common.live import EVENTS, FEEDS_KEY, health_key, live_key
from packages.common.logging import configure_logging
from packages.contracts.record import utcnow

configure_logging(config.LOG_LEVEL)
log = logging.getLogger("api")
app = FastAPI(title="OpenWatch", docs_url="/api/docs", openapi_url="/api/openapi.json")
r = aioredis.from_url(config.REDIS_URL, decode_responses=True)
archive = Archive(config.DATA_DIR)
EXPORTS = Counter("openwatch_exports_total", "Exports served", ["format"])
MAX_EXPORT_DAYS = int(os.getenv("OPENWATCH_MAX_EXPORT_DAYS", "31"))


async def feed_metas() -> list[dict]:
    return json.loads(await r.get(FEEDS_KEY) or "[]")


async def known(feeds: list[str]) -> list[str]:
    """Feed ids go into archive paths: only ever accept ids the collector registered."""
    ids = {m["id"] for m in await feed_metas()}
    bad = [f for f in feeds if f not in ids]
    if bad:
        raise HTTPException(400, f"unknown feed(s): {', '.join(bad)}")
    return feeds


@app.get("/api/health")
async def health():
    return {"ok": True, "redis": await r.ping(), "at": utcnow()}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/feeds")
async def feeds():
    metas = await feed_metas()
    healths = await r.mget([health_key(m["id"]) for m in metas]) if metas else []
    return {"feeds": [{**m, "health": json.loads(h) if h else None} for m, h in zip(metas, healths)]}


@app.get("/api/live")
async def live(feed: list[str] = Query(default=[])):
    ids = await known(feed) if feed else [m["id"] for m in await feed_metas()]
    vals = await r.mget([live_key(i) for i in ids]) if ids else []
    return {i: json.loads(v) if v else [] for i, v in zip(ids, vals)}


@app.get("/api/stream")
async def stream(request: Request):
    """SSE. `feed` events carry {feed, records, health} whenever a feed's live state changes."""
    async def gen():
        ps = r.pubsub()
        await ps.subscribe(EVENTS)
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                msg = await ps.get_message(ignore_subscribe_messages=True, timeout=15)
                if msg is None:
                    yield ": ping\n\n"  # keep proxies from closing an idle stream
                    continue
                fid = msg["data"]
                recs, h = await r.mget(live_key(fid), health_key(fid))
                yield f"event: feed\ndata: {{\"feed\":{json.dumps(fid)},\"records\":{recs or '[]'},\"health\":{h or 'null'}}}\n\n"
        finally:
            await ps.unsubscribe(EVENTS)
            await ps.aclose()
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def require_export():
    if not config.EXPORT_ENABLED:
        raise HTTPException(403, "Data export is coming soon")


def _bbox(s: str | None):
    if not s:
        return None
    try:
        b = tuple(float(x) for x in s.split(","))
    except ValueError:
        b = ()
    if len(b) != 4 or not (b[0] < b[2] and b[1] < b[3]):
        raise HTTPException(400, "bbox = lon_min,lat_min,lon_max,lat_max")
    return b


def _rows(con, sql, params) -> list[dict]:
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    out = []
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        d["geometry"] = json.loads(d["geometry"]) if d["geometry"] else None
        d["attrs"] = json.loads(d["attrs"]) if d["attrs"] else {}
        out.append(d)
    return out


@app.get("/api/history/{feed}/{id}")
async def history(feed: str, id: str, hours: float = Query(6, gt=0, le=24 * 7)):
    """Every stored version of one record: an aircraft's track, an alert's updates."""
    await known([feed])
    start = datetime.now(UTC) - timedelta(hours=hours)
    con, sql, params = archive.query([feed], start=start, ids=[id], limit=20000)
    try:
        return {"feed": feed, "id": id, "records": await asyncio.to_thread(_rows, con, sql, params)}
    finally:
        con.close()


@app.get("/api/records")
async def records(feed: list[str] = Query(...), start: datetime | None = None, end: datetime | None = None,
                  bbox: str | None = None, limit: int = Query(1000, le=10000),
                  time_field: Literal["fetched", "observed"] = "fetched"):
    """Search the archive (bulk access: gated with export)."""
    require_export()
    await known(feed)
    con, sql, params = archive.query(feed, start=start, end=end, bbox=_bbox(bbox), limit=limit, time_field=time_field)
    try:
        return {"records": await asyncio.to_thread(_rows, con, sql, params)}
    finally:
        con.close()


@app.get("/api/raw/{feed}/{sha}")
async def raw(feed: str, sha: str):
    await known([feed])
    if not all(c in "0123456789abcdef" for c in sha) or len(sha) != 64:
        raise HTTPException(400, "bad sha256")
    path = archive.raw_path(feed, sha)
    if not path:
        raise HTTPException(404, "raw bytes not kept (expired or feed doesn't keep raw)")
    name = os.path.basename(path)[:-3]
    return FileResponse(path, filename=name + ".gz", media_type="application/gzip")


class ExportReq(BaseModel):
    feeds: list[str] = Field(min_length=1)
    start: datetime
    end: datetime
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    format: Literal["geojson", "csv", "parquet"] = "geojson"
    include_unlocated: bool = True   # records with no position (press releases, space weather …) when no bbox
    include_raw: bool = False
    time_field: Literal["fetched", "observed"] = "fetched"  # window on receive time, or on the source's event time


@app.post("/api/export")
async def export(q: ExportReq):
    """Zip of the selected records + manifest.json (query, counts, source terms, sha256 per file)."""
    require_export()
    await known(q.feeds)
    if q.end <= q.start or q.end - q.start > timedelta(days=MAX_EXPORT_DAYS):
        raise HTTPException(400, f"end must be after start, window at most {MAX_EXPORT_DAYS} days")
    bbox = _bbox(",".join(map(str, q.bbox))) if q.bbox else None
    metas = {m["id"]: m for m in await feed_metas()}
    tmp = tempfile.mkdtemp(prefix="openwatch-export-")
    zpath = os.path.join(tmp, "export.zip")
    await asyncio.to_thread(_build_export, q, bbox, metas, tmp, zpath)
    EXPORTS.labels(q.format).inc()
    log.info("export", extra={"feeds": q.feeds, "start": q.start, "end": q.end, "bbox": bbox, "format": q.format})
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return FileResponse(zpath, filename=f"openwatch-export-{stamp}.zip", media_type="application/zip",
                        background=BackgroundTask(_rmtree, tmp))


def _rmtree(path: str):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def _build_export(q: ExportReq, bbox, metas: dict, tmp: str, zpath: str) -> None:
    import hashlib
    manifest = {"generated_at": utcnow(), "generator": "openwatch", "query": json.loads(q.model_dump_json()),
                "files": {}, "feeds": {}}
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fid in q.feeds:
            con, sql, params = archive.query([fid], start=q.start, end=q.end, bbox=bbox,
                                             located_only=not q.include_unlocated, time_field=q.time_field)
            out = os.path.join(tmp, f"{fid}.{q.format}")
            try:
                if q.format == "geojson":
                    _write_geojson(con, sql, params, out)
                else:
                    opts = "FORMAT parquet, COMPRESSION zstd" if q.format == "parquet" else "FORMAT csv, HEADER"
                    con.execute(f"COPY ({sql}) TO '{out}' ({opts})", params)
                n = con.execute(f"SELECT count(*) FROM ({sql})", params).fetchone()[0]
                shas = [s for (s,) in con.execute(f"SELECT DISTINCT raw_sha256 FROM ({sql}) WHERE raw_sha256 IS NOT NULL",
                                                  params).fetchall()] if q.include_raw else []
            finally:
                con.close()
            name = f"data/{fid}.{q.format}"
            z.write(out, name)
            manifest["files"][name] = hashlib.sha256(open(out, "rb").read()).hexdigest()
            m = metas.get(fid, {})
            manifest["feeds"][fid] = {"label": m.get("label"), "homepage": m.get("homepage"),
                                      "terms": m.get("terms"), "records": n, "raw_files": len(shas)}
            for sha in shas:
                p = archive.raw_path(fid, sha)
                if p:
                    z.write(p, f"raw/{fid}/{os.path.basename(p)}")
        z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
        z.writestr("README.txt", "Exported from OpenWatch. One file per feed in data/. Columns: feed, id, observed_at, "
                   "fetched_at, lon, lat, geometry (GeoJSON), kind, severity, title, attrs (source fields, JSON), "
                   "raw_sha256 (original response in raw/ when included). Each feed's licence/terms are in "
                   "manifest.json and apply to its data.\n")


def _write_geojson(con, sql, params, out: str) -> None:
    """Streamed so a big window never sits in memory."""
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    with open(out, "w", encoding="utf-8") as f:
        f.write('{"type":"FeatureCollection","features":[\n')
        first = True
        while rows := cur.fetchmany(5000):
            for row in rows:
                d = dict(zip(cols, row))
                geom = json.loads(d.pop("geometry")) if d["geometry"] else (
                    {"type": "Point", "coordinates": [d["lon"], d["lat"]]} if d["lon"] is not None else None)
                d["attrs"] = json.loads(d["attrs"]) if d["attrs"] else {}
                f.write(("" if first else ",\n") + json.dumps({"type": "Feature", "geometry": geom, "properties": d},
                                                              ensure_ascii=False, default=str))
                first = False
        f.write("\n]}\n")


TOMTOM_KEY = os.getenv("TOMTOM_KEY", "")
_tiles = httpx.AsyncClient(timeout=15)


@app.get("/api/tiles/traffic/{z}/{x}/{y}.png")
async def traffic_tile(z: int, x: int, y: int):
    """TomTom traffic-flow raster, proxied so the key stays server side. 404 when no key is set."""
    if not TOMTOM_KEY:
        raise HTTPException(404, "TOMTOM_KEY not set")
    if not (0 <= z <= 22 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        raise HTTPException(400, "bad tile")
    t = await _tiles.get(f"https://api.tomtom.com/traffic/map/4/tile/flow/relative0/{z}/{x}/{y}.png",
                         params={"key": TOMTOM_KEY, "tileSize": 256})
    if t.status_code != 200:
        raise HTTPException(502, f"tomtom {t.status_code}")
    return Response(t.content, media_type="image/png", headers={"Cache-Control": "public, max-age=60"})


@app.get("/api/config")
async def ui_config():
    return {"traffic_tiles": bool(TOMTOM_KEY), "global": config.SCOPE == "global", "export": config.EXPORT_ENABLED}
