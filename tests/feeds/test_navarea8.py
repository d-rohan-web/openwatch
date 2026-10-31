from pathlib import Path

from apps.collector.feeds.navarea8 import parse

TEXT = (Path(__file__).parent.parent / "fixtures" / "navarea8.txt").read_text()


def test_parse():
    rs = {r["id"]: r for r in parse(TEXT)}
    assert list(rs) == ["161/23", "733/23", "180/24", "593/25", "599/25", "601/25", "618/25"]  # 615/25 is the list itself
    wreck = rs["733/23"]  # coordinate split over a line break
    assert wreck["kind"] == "navwarn" and wreck["severity"] is None
    assert (wreck["lat"], wreck["lon"]) == (18.24433, 72.886) and wreck["geometry"] is None
    assert wreck["observed_at"] == "2023-08-19T10:02:00+00:00" and wreck["attrs"]["list_as_on"] == "2025-07-07"
    assert rs["180/24"]["geometry"]["type"] == "MultiPoint"
    fire = rs["618/25"]
    assert fire["kind"] == "firing" and fire["severity"] == "advisory"
    assert fire["geometry"]["coordinates"][0][0] == [84.08333, 17.96667] and len(fire["geometry"]["coordinates"][0]) == 5
    assert fire["attrs"]["cancel_at"] == "2025-07-09T07:30:00+00:00"
    assert rs["593/25"]["geometry"]["coordinates"][0][0] == [91.39167, 21.625]  # "BOUNDED WITHIN lat TO lat AND lon TO lon"
    assert rs["601/25"]["geometry"]["type"] == "MultiPolygon" and len(rs["601/25"]["geometry"]["coordinates"]) == 5
    assert rs["599/25"]["kind"] == "navwarn"
