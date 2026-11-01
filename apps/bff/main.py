"""Backend for frontend: the only API the browser can reach (/ui/*).

It calls the core API (apps/api) over the internal network, so the core API, its OpenAPI docs and the archive search
stay private. Routes are an allow-list of what the UI uses, shaped for it (one bootstrap call for the first frame).
Upstream failures come back as a plain 502 so internals never reach the page.
"""
from __future__ import annotations

import asyncio
import os
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

API_URL = os.getenv("OPENWATCH_API_URL", "http://api:8000")
PASS_HEADERS = {"content-type", "content-disposition", "cache-control"}

app = FastAPI(title="OpenWatch BFF", docs_url=None, redoc_url=None, openapi_url=None)
client = httpx.AsyncClient(base_url=API_URL, timeout=httpx.Timeout(30, connect=5))


async def call(method: str, path: str, **kw) -> httpx.Response:
    try:
        r = await client.request(method, path, **kw)
    except httpx.HTTPError:
        raise HTTPException(502, "unavailable") from None
    if r.status_code >= 500:
        raise HTTPException(502, "unavailable")
    return r


def relay(r: httpx.Response) -> Response:
    """The core API's answer as is: status (4xx details are meant for users), body and the headers that matter."""
    return Response(r.content, r.status_code, headers={k: v for k, v in r.headers.items() if k in PASS_HEADERS})


def seg(s: str) -> str:
    return quote(s, safe="")  # one path segment: never lets "..", "/" or "?" reach the core API's routing


@app.get("/ui/health")
async def health():
    return {"ok": True}


@app.get("/ui/bootstrap")
async def bootstrap():
    """Everything the page needs for its first frame, in one request."""
    cfg, feeds, live = await asyncio.gather(call("GET", "/api/config"), call("GET", "/api/feeds"), call("GET", "/api/live"))
    if any(r.status_code != 200 for r in (cfg, feeds, live)):
        raise HTTPException(502, "unavailable")
    return {"config": cfg.json(), "feeds": feeds.json()["feeds"], "live": live.json()}


@app.get("/ui/feeds")
async def feeds():
    return relay(await call("GET", "/api/feeds"))


@app.get("/ui/window/{feed}")
async def window(feed: str, hours: float = 6):
    return relay(await call("GET", f"/api/window/{seg(feed)}", params={"hours": hours}))


@app.get("/ui/history/{feed}/{id}")
async def history(feed: str, id: str, hours: float = 6):
    return relay(await call("GET", f"/api/history/{seg(feed)}/{seg(id)}", params={"hours": hours}))


@app.get("/ui/raw/{feed}/{sha}")
async def raw(feed: str, sha: str):
    return relay(await call("GET", f"/api/raw/{seg(feed)}/{seg(sha)}"))


@app.get("/ui/tiles/traffic/{z}/{x}/{y}.png")
async def traffic(z: int, x: int, y: int):
    return relay(await call("GET", f"/api/tiles/traffic/{z}/{x}/{y}.png"))


@app.post("/ui/export")
async def export(request: Request):
    # ponytail: the zip is buffered in memory; stream it if exports grow past what the VM's RAM is comfortable with
    return relay(await call("POST", "/api/export", content=await request.body(), headers={"content-type": "application/json"}))


@app.get("/ui/stream")
async def stream():
    """The live SSE stream, relayed chunk by chunk. If the core API is down the browser is told to retry."""
    async def gen():
        try:
            async with client.stream("GET", "/api/stream", timeout=httpx.Timeout(None, connect=5)) as r:
                if r.status_code != 200:
                    yield b"retry: 3000\n\n"
                    return
                async for chunk in r.aiter_raw():
                    yield chunk
        except httpx.HTTPError:
            yield b"retry: 3000\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
