"""One-off: India's maritime zones from Marine Regions (VLIZ, CC BY 4.0) → apps/frontend/public/geo/maritime.geojson.

Territorial sea (12 nm), contiguous zone (24 nm) and Exclusive Economic Zone (200 nm), mainland and Andaman & Nicobar.

uv run --with shapely python scripts/build_maritime.py <dir to cache the downloads in>
"""
import json
import os
import sys
import urllib.parse
import urllib.request

from shapely.geometry import mapping, shape

cache = sys.argv[1]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WFS = "https://geo.vliz.be/geoserver/MarineRegions/wfs?"
ZONES = [("eez", "EEZ", "Exclusive Economic Zone (200 nm)"), ("eez_24nm", "CZ", "Contiguous zone (24 nm)"),
         ("eez_12nm", "TS", "Territorial sea (12 nm)")]


def get(layer: str) -> dict:
    path = os.path.join(cache, f"{layer}.json")
    if not os.path.exists(path):
        q = urllib.parse.urlencode({"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": f"MarineRegions:{layer}",
                                    "cql_filter": "sovereign1='India'", "outputFormat": "application/json"})
        req = urllib.request.Request(WFS + q, headers={"User-Agent": "openwatch build script"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    return json.load(open(path))


feats = []
for layer, zone, label in ZONES:
    for f in get(layer)["features"]:
        p = f["properties"]
        g = shape(f["geometry"]).buffer(0).simplify(0.01, preserve_topology=True)
        feats.append({"type": "Feature", "properties": {"zone": zone, "label": label, "name": p.get("geoname"),
                      "area_km2": p.get("area_km2"), "source": "Marine Regions (VLIZ), CC BY 4.0"},
                      "geometry": json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), 3))})
out = os.path.join(root, "apps/frontend/public/geo/maritime.geojson")
json.dump({"type": "FeatureCollection", "features": feats}, open(out, "w"), separators=(",", ":"))
print(len(feats), "zones →", out, os.path.getsize(out) // 1024, "KB")

# The India view (what the UI keeps when India scope is on) = India's land (+ ~50 km) ∪ its EEZ.
from shapely.ops import unary_union  # noqa: E402

india = shape(json.load(open(os.path.join(root, "apps/frontend/public/geo/india.geojson")))["features"][0]["geometry"]).buffer(0)
eez = [shape(f["geometry"]).buffer(0) for f in get("eez")["features"]]
view = unary_union([india.buffer(0.5), *[e.buffer(0.1) for e in eez]]).simplify(0.05)
json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "India + EEZ"},
           "geometry": json.loads(json.dumps(mapping(view)), parse_float=lambda x: round(float(x), 3))}]},
          open(os.path.join(root, "apps/frontend/public/geo/scope.geojson"), "w"), separators=(",", ":"))
print("scope.geojson = India + EEZ")
