"""GDELT 2.0 Events: machine-coded conflict and protest events located in India, from the last hour of news."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timedelta, UTC
from urllib.parse import urlsplit

from apps.collector.feed import Feed
from packages.common.geo import GLOBAL
from packages.contracts.record import record

# The GEO API is gone (404) and the DOC API returns {} for every query, so read the raw 15-min event exports.
LAST = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"
EXPORT = "https://data.gdeltproject.org/gdeltv2/{}.export.CSV.zip"
# CAMEO root codes for QuadClass 3 (verbal conflict) and 4 (material conflict)
THEME = {"10": "demand", "11": "disapprove", "12": "reject", "13": "threaten", "14": "protest", "15": "force_posture",
         "16": "reduce_relations", "17": "coerce", "18": "assault", "19": "fight", "20": "mass_violence"}
# Export columns (http://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf)
ID, A1, A2, CODE, ROOT, QUAD, GOLDSTEIN, MENTIONS, TONE = 0, 6, 16, 26, 28, 29, 30, 31, 34
GEO_TYPE, PLACE, CC, ADM1, LAT, LON, ADDED, URL = 51, 52, 53, 54, 56, 57, 59, 60

_files: dict[str, list[dict]] = {}  # export timestamp → parsed records; exports never change


def severity(root: str) -> str:
    return "warning" if root in ("18", "19", "20") else "advisory" if root in ("14", "15", "16", "17") else "info"


def slug_title(url: str) -> str | None:
    # No headline in the export: the longest hyphenated path segment usually is one.
    seg = max(urlsplit(url).path.split("/"), key=lambda s: s.count("-"), default="")
    words = seg.rsplit(".", 1)[0].replace("_", "-").split("-")
    return " ".join(words).capitalize() if len(words) >= 3 else None


def parse(tsv: str) -> list[dict]:
    best: dict[str, list] = {}  # one record per article: its most conflictual event
    for f in csv.reader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(f) < 61 or (not GLOBAL and f[CC] != "IN") or f[QUAD] not in ("3", "4"):
            continue
        if f[URL] not in best or float(f[GOLDSTEIN]) < float(best[f[URL]][GOLDSTEIN]):
            best[f[URL]] = f
    out = []
    for url, f in best.items():
        theme = THEME.get(f[ROOT], f[ROOT])
        located = f[GEO_TYPE] != "1" and f[LAT] and f[LON]  # type 1 = country centroid, not a place
        actors = " / ".join(a.title() for a in (f[A1], f[A2]) if a)
        out.append(record(f[ID], title=slug_title(url) or f"{theme.replace('_', ' ').title()}: {actors or f[PLACE]}",
                          kind=theme, lon=float(f[LON]) if located else None, lat=float(f[LAT]) if located else None,
                          observed_at=datetime.strptime(f[ADDED], "%Y%m%d%H%M%S"), severity=severity(f[ROOT]),
                          url=url, domain=urlsplit(url).hostname, tone=round(float(f[TONE]), 2), theme=theme,
                          cameo=f[CODE], goldstein=float(f[GOLDSTEIN]), mentions=int(f[MENTIONS]),
                          actor1=f[A1] or None, actor2=f[A2] or None, place=f[PLACE], adm1=f[ADM1] or None))
    return out


async def fetch(ctx) -> list[dict]:
    latest = (await ctx.get(LAST, raw_ext="txt")).text.split("\n")[0].rsplit("/", 1)[1][:14]
    t0 = datetime.strptime(latest, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    wanted = [(t0 - timedelta(minutes=15 * i)).strftime("%Y%m%d%H%M%S") for i in range(4)]  # last hour
    for ts in wanted:
        if ts not in _files:
            z = zipfile.ZipFile(io.BytesIO((await ctx.get(EXPORT.format(ts), raw_ext="zip")).content))
            _files[ts] = parse(z.read(z.namelist()[0]).decode("utf-8", "replace"))
    for ts in set(_files) - set(wanted):
        del _files[ts]
    return [r for ts in wanted for r in _files[ts]]


FEED = Feed(id="gdelt", label="News events (GDELT)", section="govt", homepage="https://www.gdeltproject.org/",
            terms="GDELT Project: free and open, unrestricted use with citation of gdeltproject.org",
            every=900, fetch=fetch, snapshot=True)
