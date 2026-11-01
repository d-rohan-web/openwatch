"""One-off: border layers from India's official outline + Natural Earth 10m (public domain).

  apps/frontend/public/geo/borders.geojson    India's official land boundary split by neighbour, with MHA lengths
  apps/frontend/public/geo/defacto.geojson    LoC / LAC / Siachen lines (de facto, approximate; India does not recognise
                                              them as boundaries), from Natural Earth's FCLASS_IN = "Unrecognized"
  apps/frontend/public/geo/neighbours.geojson every other country's land borders (outside India) + labels

uv run --with pyshp --with shapely python scripts/build_borders.py <dir with ne_10m_admin_0_countries.* and
  ne_10m_admin_0_boundary_lines_land.*>   (run after build_geo.py: reads public/geo/india.geojson)
"""
import json
import os
import sys

import shapefile
from shapely.geometry import box, mapping, shape
from shapely.ops import linemerge, unary_union

src = sys.argv[1]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
geo = os.path.join(root, "apps/frontend/public/geo")
REGION = box(-180, -85, 180, 85)  # the whole globe
# Ministry of Home Affairs (Department of Border Management) land boundary lengths, km
MHA_KM = {"Bangladesh": 4096.7, "China": 3488, "Pakistan": 3323, "Nepal": 1751, "Myanmar": 1643, "Bhutan": 699,
          "Afghanistan": 106}


def rounded(g, nd=4):
    return json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), nd))


def records(name):
    r = shapefile.Reader(os.path.join(src, name))
    fields = [f[0] for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        yield dict(zip(fields, sr.record)), shape(sr.shape.__geo_interface__)


india = shape(json.load(open(os.path.join(geo, "india.geojson")))["features"][0]["geometry"]).buffer(0)
outline = india.boundary
countries = {d["ADMIN"]: (d, g.buffer(0)) for d, g in records("ne_10m_admin_0_countries")}

# 1. official boundary, segment by neighbour (coast = whatever touches no neighbour, left out)
feats = []
for n, km in MHA_KM.items():
    seg = outline.intersection(countries[n][1].buffer(0.08))
    seg = linemerge(seg) if seg.geom_type == "MultiLineString" else seg
    if not seg.is_empty:
        feats.append({"type": "Feature", "properties": {"neighbour": n, "label": f"India – {n}", "length_km": km,
                      "source": "Official boundary (Survey of India via datameet); length: MHA"},
                      "geometry": rounded(seg.simplify(0.002))})
json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(geo, "borders.geojson"), "w"), separators=(",", ":"))

# 2. de facto lines inside India's claim
LABEL = {("India", "Pakistan"): "Line of Control (de facto)", ("China", "India"): "Line of Actual Control, approx. (de facto)"}
defacto = []
for d, g in records("ne_10m_admin_0_boundary_lines_land"):
    pair = tuple(sorted((d["ADM0_LEFT"], d["ADM0_RIGHT"])))
    if d["FCLASS_IN"] != "Unrecognized" or not g.intersects(india.buffer(0.2)):
        continue
    label = LABEL.get(pair) or ("Siachen, AGPL approx. (de facto)" if "Siachen Glacier" in pair else f"{' / '.join(pair)} (de facto)")
    defacto.append({"type": "Feature", "properties": {"label": label, "class": d["FEATURECLA"], "sides": " / ".join(pair),
                    "note": "Not recognised by India as a boundary; shown for situational awareness only"},
                    "geometry": rounded(g)})
json.dump({"type": "FeatureCollection", "features": defacto}, open(os.path.join(geo, "defacto.geojson"), "w"), separators=(",", ":"))

# 3. other countries' land borders, outside India's claim, plus every country's label (rank: Natural Earth LABELRANK, 1 = biggest)
lines = []
for d, g in records("ne_10m_admin_0_boundary_lines_land"):
    if "India" in (d["ADM0_LEFT"], d["ADM0_RIGHT"]) or not g.intersects(REGION):
        continue
    if d["FCLASS_IN"] not in ("", "International boundary"):
        continue
    rest = g.intersection(REGION).difference(india.buffer(0.03))
    if not rest.is_empty and rest.length > 0.05:
        lines.append(rest)
nfeats = [{"type": "Feature", "properties": {"kind": "border"}, "geometry": rounded(unary_union(lines).simplify(0.01), 3)}]
for name, (d, g) in countries.items():
    if d.get("LABEL_X") is not None:
        p = (float(d["LABEL_X"]), float(d["LABEL_Y"]))
        if name == "India" or not india.contains(shape({"type": "Point", "coordinates": p})):
            nfeats.append({"type": "Feature", "properties": {"kind": "label", "name": d["NAME"], "rank": int(d["LABELRANK"])},
                           "geometry": {"type": "Point", "coordinates": [round(p[0], 3), round(p[1], 3)]}})
json.dump({"type": "FeatureCollection", "features": nfeats}, open(os.path.join(geo, "neighbours.geojson"), "w"), separators=(",", ":"))
print(len(feats), "border segments;", len(defacto), "de facto lines;", len(nfeats) - 1, "country labels")
