"""BFF: what the browser can reach, how it maps onto the core API, and that internals never leak."""
import httpx
from fastapi.testclient import TestClient

from apps.bff import main

seen: list[str] = []


def core(request: httpx.Request) -> httpx.Response:
    """A fake core API."""
    seen.append(request.url.raw_path.decode())
    path = request.url.path
    if path == "/api/config":
        return httpx.Response(200, json={"traffic_tiles": False, "global": False, "export": False})
    if path == "/api/feeds":
        return httpx.Response(200, json={"feeds": [{"id": "usgs_quakes"}]})
    if path == "/api/live":
        return httpx.Response(200, json={"usgs_quakes": [{"id": "q1"}]})
    if path.startswith("/api/window/"):
        return httpx.Response(200, json={"records": []}, headers={"x-internal": "secret", "cache-control": "no-store"})
    if path == "/api/export":
        return httpx.Response(403, json={"detail": "Data export is coming soon"})
    if path.startswith("/api/raw/"):
        return httpx.Response(500, text="Traceback: /data/raw/... duckdb error")
    return httpx.Response(404, json={"detail": "Not Found"})


def ui(monkeypatch) -> TestClient:
    seen.clear()
    monkeypatch.setattr(main, "client", httpx.AsyncClient(base_url="http://api", transport=httpx.MockTransport(core)))
    return TestClient(main.app)


def test_bootstrap_is_one_call_for_the_first_frame(monkeypatch):
    d = ui(monkeypatch).get("/ui/bootstrap").json()
    assert d == {"config": {"traffic_tiles": False, "global": False, "export": False},
                 "feeds": [{"id": "usgs_quakes"}], "live": {"usgs_quakes": [{"id": "q1"}]}}


def test_relays_body_status_and_only_safe_headers(monkeypatch):
    c = ui(monkeypatch)
    r = c.get("/ui/window/usgs_quakes", params={"hours": 12})
    assert r.status_code == 200 and r.json() == {"records": []}
    assert "x-internal" not in r.headers and r.headers["cache-control"] == "no-store"
    assert seen[-1] == "/api/window/usgs_quakes?hours=12.0"
    r = c.post("/ui/export", json={"feeds": ["aircraft"]})
    assert r.status_code == 403 and r.json()["detail"] == "Data export is coming soon"  # user-facing 4xx kept


def test_upstream_errors_are_hidden(monkeypatch):
    r = ui(monkeypatch).get("/ui/raw/aircraft/" + "a" * 64)
    assert r.status_code == 502 and r.json() == {"detail": "unavailable"} and "Traceback" not in r.text


def test_ids_cannot_escape_their_segment(monkeypatch):
    ui(monkeypatch).get("/ui/history/aircraft/a%3Fhours=99%26b")  # id "a?hours=99&b"
    assert seen[-1] == "/api/history/aircraft/a%3Fhours%3D99%26b?hours=6"


def test_only_ui_routes_exist(monkeypatch):
    c = ui(monkeypatch)
    for path in ("/api/live", "/ui/records", "/docs", "/openapi.json", "/ui/../api/live"):
        assert c.get(path).status_code == 404, path
    assert seen == []  # nothing was forwarded
