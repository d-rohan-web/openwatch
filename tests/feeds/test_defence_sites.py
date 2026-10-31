from pathlib import Path

from apps.collector.feeds.defence_sites import parse

FIX = Path(__file__).parent.parent / "fixtures" / "defence_sites.json"


def test_parse():
    rs = {r["id"]: r for r in parse(FIX.read_bytes())}
    assert "Q13117117" not in rs  # Sangram Durg: a fort tagged military base
    h = rs["Q3274626"]
    assert h["kind"] == "airbase" and h["attrs"]["icao"] == "VIDX" and h["attrs"]["branch"] == "air_force"
    assert rs["Q5972537"]["kind"] == "naval_base" and rs["Q5972537"]["attrs"]["branch"] == "navy"
    assert rs["Q107675717"]["attrs"]["branch"] == "navy"  # INS Angre: no operator, branch from the name
    assert rs["Q5071085"]["attrs"]["branch"] == "army" and rs["Q1192604"]["kind"] == "cantonment"
    assert rs["Q3630909"]["kind"] == "academy" and "branch" not in rs["Q3630909"]["attrs"]
