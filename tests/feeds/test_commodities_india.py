import json
from pathlib import Path

from apps.collector.feeds.commodities_india import parse_brent, parse_ibja


def test_parse():
    gold, silver = parse_ibja(Path("tests/fixtures/commodities_india.html").read_text())
    assert gold["id"] == "GOLD 999" and gold["attrs"]["value"] == 140054 and gold["attrs"]["change"] == -2201
    assert gold["attrs"]["as_of"] == "2026-10-30" and gold["severity"] == "info"
    assert silver["attrs"]["unit"] == "INR/kg" and silver["severity"] == "warning"  # -4.8 %
    [brent] = parse_brent(json.loads(Path("tests/fixtures/commodities_india_brent.json").read_text()))
    assert brent["title"] == "BRENT 113.43 ▲2.37%" and brent["severity"] == "advisory"
