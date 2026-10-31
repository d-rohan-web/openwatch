"""One-off: build the static geo files we ship from datameet/maps (https://github.com/datameet/maps).

  apps/frontend/public/geo/india.geojson   official outline of India (Country/india-composite.geojson, CC0), simplified
  apps/frontend/public/geo/mask.geojson      the world minus India, to dim everything outside it
  apps/frontend/public/geo/scope.geojson     (rewritten by build_maritime.py as India + EEZ)
  apps/frontend/public/geo/districts.geojson  2011 census districts (Districts/Census_2011, CC BY 4.0), simplified
  packages/common/data/districts.json       [{name, state, lon, lat}] for placing district-level alerts
  apps/frontend/public/geo/states.geojson    current states/UTs (States/Admin2, CC BY 4.0) with bbox, for click-to-fly

uv run --with pyshp --with shapely python scripts/build_geo.py <dir with india-composite.geojson, 2011_Dist.* and Admin2.*>
"""
import json
import os
import sys

import shapefile
from shapely.geometry import box, mapping, shape

src = sys.argv[1]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
geo = os.path.join(root, "apps/frontend/public/geo")
os.makedirs(geo, exist_ok=True)
os.makedirs(os.path.join(root, "packages/common/data"), exist_ok=True)


def rounded(g, nd=4):
    return json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), nd))


india = json.load(open(os.path.join(src, "india-composite.geojson")))
outline = shape(india["features"][0]["geometry"]).simplify(0.003, preserve_topology=True)
json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "India"},
          "geometry": rounded(outline)}]}, open(os.path.join(geo, "india.geojson"), "w"), separators=(",", ":"))
json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
          "geometry": rounded(box(-180, -85, 180, 85).difference(outline.buffer(0)))}]},
          open(os.path.join(geo, "mask.geojson"), "w"), separators=(",", ":"))
json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
          "geometry": rounded(outline.buffer(0).buffer(1.8).simplify(0.1), 3)}]},
          open(os.path.join(geo, "scope.geojson"), "w"), separators=(",", ":"))

r = shapefile.Reader(os.path.join(src, "2011_Dist"))
fields = [f[0] for f in r.fields[1:]]
feats, cents = [], []
for sr in r.iterShapeRecords():
    p = dict(zip(fields, sr.record))
    g = shape(sr.shape.__geo_interface__)
    if g.is_empty:
        continue
    name, state = p.get("DISTRICT", "").strip(), p.get("ST_NM", "").strip()
    c = g.representative_point()
    cents.append({"name": name, "state": state, "lon": round(c.x, 4), "lat": round(c.y, 4)})
    feats.append({"type": "Feature", "properties": {"name": name, "state": state},
                  "geometry": rounded(g.simplify(0.01, preserve_topology=True), 3)})
json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(geo, "districts.geojson"), "w"),
          separators=(",", ":"))
json.dump(cents, open(os.path.join(root, "packages/common/data/districts.json"), "w"), ensure_ascii=False, indent=0)
print(len(feats), "districts;", fields)

st = shapefile.Reader(os.path.join(src, "Admin2"))
sfeats = []
for sr in st.iterShapeRecords():
    g = shape(sr.shape.__geo_interface__).buffer(0)
    tol = 0.002 if g.area < 0.2 else 0.01  # keep small UTs (Chandigarh, Delhi) recognisable
    sfeats.append({"type": "Feature", "properties": {"name": sr.record[0].strip(), "bbox": [round(v, 3) for v in g.bounds]},
                   "geometry": rounded(g.simplify(tol, preserve_topology=True), 3)})
json.dump({"type": "FeatureCollection", "features": sfeats}, open(os.path.join(geo, "states.geojson"), "w"), separators=(",", ":"))
print(len(sfeats), "states")
