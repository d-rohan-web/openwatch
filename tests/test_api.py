"""API guards that don't need Redis: bulk data access stays closed until export is enabled."""
from datetime import datetime, timedelta, UTC

from fastapi.testclient import TestClient

from packages.common.archive import Archive
from packages.contracts.record import iso, record

from apps.api import main


def test_export_and_records_are_closed_by_default(monkeypatch):
    monkeypatch.setattr(main.config, "EXPORT_ENABLED", False)
    c = TestClient(main.app)
    r = c.post("/api/export", json={"feeds": ["aircraft"], "start": "2026-01-01T00:00:00Z", "end": "2026-01-02T00:00:00Z"})
    assert r.status_code == 403 and "coming soon" in r.json()["detail"]
    assert c.get("/api/records", params={"feed": "aircraft"}).status_code == 403


def test_raw_rejects_bad_sha(monkeypatch):
    async def known(feeds):
        return feeds
    monkeypatch.setattr(main, "known", known)
    assert TestClient(main.app).get("/api/raw/aircraft/not-a-sha").status_code == 400


def test_window_returns_latest_version_per_record(monkeypatch, tmp_path):
    async def known(feeds):
        return feeds
    a = Archive(str(tmp_path))
    now = datetime.now(UTC)
    def put(id, sev, lon=77, ago=0):
        a.append("q", [{**record(id, title=id, kind="earthquake", lon=lon, lat=lon and 28, observed_at=now, sev=sev),
                         "feed": "q", "fetched_at": iso(now - timedelta(minutes=ago)), "raw_sha256": None}], store_all=False)
    put("a", 1, ago=10); put("a", 2); put("b", 1); put("c", 1, lon=None)
    monkeypatch.setattr(main, "known", known)
    monkeypatch.setattr(main, "archive", a)
    recs = TestClient(main.app).get("/api/window/q", params={"hours": 6}).json()["records"]
    assert sorted((r["id"], r["attrs"]["sev"]) for r in recs) == [("a", 2), ("b", 1)]  # latest a; unlocated c left out
    assert TestClient(main.app).get("/api/window/q", params={"hours": 48}).status_code == 422


def test_stream_events_leave_records_out_when_only_health_changed():
    full = main.sse_event("usgs_quakes", '[{"id":"q1"}]', '{"state":"OK"}')
    assert full == 'event: feed\ndata: {"feed":"usgs_quakes","records":[{"id":"q1"}],"health":{"state":"OK"}}\n\n'
    assert main.sse_event("usgs_quakes", None, None) == 'event: feed\ndata: {"feed":"usgs_quakes","health":null}\n\n'
