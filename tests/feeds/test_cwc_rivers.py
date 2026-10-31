import json
from pathlib import Path

from apps.collector.feeds.cwc_rivers import parse, severity


def test_parse():
    rs = {r["id"]: r for r in parse(json.loads((Path(__file__).parents[1] / "fixtures/cwc_rivers.json").read_text()))}
    assert len(rs) == 3
    m = rs["060-erdbwn"]  # 6.58 m: above danger 6.5, below HFL 7.31
    assert m["severity"] == "warning" and m["attrs"]["trend"] == "rising" and m["attrs"]["hfl_m"] == 7.31
    assert (m["lon"], m["lat"]) == (87.06, 21.66) and m["attrs"]["station"] == "Mathani Road Bridge"
    assert rs["024-mgd5pat"]["severity"] == "advisory"
    assert severity(8, 6, 6.5, 7.31, "DANGER") == "critical"
    assert severity(None, None, None, None, "EXTREME") == "critical"
