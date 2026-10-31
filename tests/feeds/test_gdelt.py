from pathlib import Path

from apps.collector.feeds.gdelt import parse


def test_parse():
    recs = parse(Path("tests/fixtures/gdelt.tsv").read_text())
    assert len(recs) == 6  # India conflict events only; cooperation and foreign rows dropped
    byurl = {r["attrs"]["url"]: r for r in recs}
    r = byurl["https://www.tribuneindia.com/news/india/hardeep-nijjar-aides-car-set-ablaze-after-pro-khalistan-rally-in-canada/"]
    assert r["kind"] == "assault" and r["severity"] == "warning" and r["attrs"]["domain"] == "www.tribuneindia.com"
    assert r["title"].startswith("Hardeep nijjar aides car") and r["lat"] is not None
    toi = next(r for u, r in byurl.items() if "articleshow" in u)
    assert toi["title"] == "36 bdeshis detained in dhubri after illegal entry"
    assert all(r["observed_at"].startswith("2026-10-30T21:45") for r in recs)
