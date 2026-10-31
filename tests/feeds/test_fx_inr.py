import json
from pathlib import Path

from apps.collector.feeds.fx_inr import parse


def test_parse():
    d = json.loads(Path("tests/fixtures/fx_inr.json").read_text())
    recs = {r["id"]: r for r in parse(d["latest"], d["prev"])}
    assert set(recs) == {"USD/INR", "EUR/INR", "GBP/INR", "JPY/INR", "CNY/INR", "AED/INR"}
    usd, aed = recs["USD/INR"]["attrs"], recs["AED/INR"]["attrs"]
    assert 94 < usd["value"] < 96 and usd["unit"] == "INR" and usd["previous_date"] == "2026-10-29"
    assert abs(aed["value"] * 3.6725 - usd["value"]) < 1e-4 and aed["derived"]
