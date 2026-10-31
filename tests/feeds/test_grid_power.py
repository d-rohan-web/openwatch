from pathlib import Path

from apps.collector.feeds.grid_power import parse, severity


def test_parse():
    [r] = parse(Path("tests/fixtures/grid_power.html").read_text())
    a = r["attrs"]
    assert a["demand_met_mw"] == 169291 and a["thermal_mw"] == 146222 and a["transnational_mw"] == -273
    assert a["storage_mw"] > 0 and r["lon"] is None and r["severity"] == "info"
    assert [severity(h) for h in (50.0, 49.88, 50.1, 49.7)] == ["info", "advisory", "advisory", "warning"]
