"""Place names → points, for sources that only give a district/state name. Data: scripts/build_geo.py (datameet, CC BY 4.0)."""
from __future__ import annotations

import json
import os
import re
from functools import cache

from packages.common import config

INDIA_BBOX = (68.0, 6.0, 98.0, 37.5)          # lon_min, lat_min, lon_max, lat_max: mainland + islands
REGION_BBOX = (40.0, -15.0, 105.0, 42.0)      # India + neighbours + Indian Ocean (NAVAREA VIII and around)
WORLD_BBOX = (-180.0, -90.0, 180.0, 90.0)
GLOBAL = config.SCOPE == "global"
COVERAGE = WORLD_BBOX if GLOBAL else REGION_BBOX  # what region-filtered feeds keep (OPENWATCH_SCOPE)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


# Post-2011 / alternate state names → the state name districts.json files them under
STATES = {"telangana": "andhrapradesh", "ladakh": "jammukashmir", "jammuandkashmir": "jammukashmir",
          "arunachalpradesh": "arunanchalpradesh", "delhi": "nctofdelhi", "uttrakhand": "uttarakhand",
          "andamanandnicobarislands": "andamannicobarisland", "andamannicobarislands": "andamannicobarisland",
          "dadraandnagarhaveli": "dadaranagarhavelli", "damananddiu": "damandiu"}


def _data(name: str):
    with open(os.path.join(os.path.dirname(__file__), "data", name), encoding="utf-8") as f:
        return json.load(f)


def _state(s: str) -> str:
    s = _norm(s)
    return STATES.get(s, s)


@cache
def _districts() -> dict[str, dict]:
    """Every row, keyed name|state (district names repeat across states: Bijapur, Aurangabad, East …)."""
    return {f"{_norm(r['name'])}|{_state(r['state'])}": r for r in _data("districts.json")}


@cache
def _by_name() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in _districts().values():
        out.setdefault(_norm(r["name"]), []).append(r)
    return out


@cache
def _aliases() -> dict[str, str | list[str]]:
    """Normalized source spelling / post-2011 district → 2011 name (or [name, state] where the name repeats)."""
    return _data("district_aliases.json")


def district(name: str, state: str | None = None) -> dict | None:
    """{name, state, lon, lat} for a district name (spelling-insensitive), or None. 2011 census district names;
    newer districts resolve to their 2011 parent. `state` picks between same-named districts."""
    key = _norm(name)
    alias = _aliases().get(key)
    if isinstance(alias, list):
        key, state = _norm(alias[0]), alias[1]
    elif alias:
        key = _norm(alias)
    rows = _by_name().get(key, [])
    if state and len(rows) > 1:
        return next((r for r in rows if _state(r["state"]) == _state(state)), rows[0])
    return rows[0] if rows else None


def in_bbox(lon: float, lat: float, bbox=None) -> bool:
    bbox = bbox or COVERAGE
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]
