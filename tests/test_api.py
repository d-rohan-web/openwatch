"""API guards that don't need Redis: bulk data access stays closed until export is enabled."""
from fastapi.testclient import TestClient

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
