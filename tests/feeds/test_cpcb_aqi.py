import json
from pathlib import Path

from apps.collector.feeds.cpcb_aqi import parse

# Fixture follows the documented data.gov.in response shape (no API key was available for a live sample).


def test_parse():
    d = json.loads((Path(__file__).parents[1] / "fixtures/cpcb_aqi.json").read_text())
    rs = {r["id"]: r for r in parse(d["records"])}
    assert len(rs) == 3
    a = rs["Anand Vihar, Delhi - DPCC"]
    assert a["attrs"]["aqi"] == 348 and a["attrs"]["band"] == "very poor" and a["severity"] == "warning"
    assert a["attrs"]["prominent"] == "PM2.5" and "OZONE" not in a["attrs"]["pollutants"]
    assert a["observed_at"] == "2026-10-31T04:30:00+00:00"
    assert rs["Hebbal, Bengaluru - KSPCB"]["severity"] == "info"
    assert rs["Loni, Ghaziabad - UPPCB"]["severity"] == "critical"
