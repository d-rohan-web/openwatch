import json
from datetime import datetime, UTC
from pathlib import Path

from apps.collector.feeds.markets_india import market_open, move_severity, parse


def test_parse():
    d = json.loads(Path("tests/fixtures/markets_india.json").read_text())
    recs = {r["id"]: r for r in parse(d, datetime(2026, 10, 31, 6, tzinfo=UTC))}  # Saturday
    assert set(recs) == {"SENSEX", "NIFTY 50", "NIFTY BANK", "INDIA VIX"}
    s = recs["SENSEX"]
    assert s["title"] == "SENSEX 74,459.53 ▲0.42%" and s["lon"] is None and s["severity"] == "info"
    assert s["attrs"]["change"] == 308.49 and s["attrs"]["market_state"] == "closed" and s["attrs"]["currency"] == "INR"
    assert recs["NIFTY BANK"]["title"].endswith("▼0.41%")
    assert [move_severity(p) for p in (1.9, -2.0, 4.5)] == ["info", "advisory", "warning"]
    assert market_open(datetime(2026, 10, 30, 5, tzinfo=UTC)) and not market_open(datetime(2026, 10, 30, 11, tzinfo=UTC))
