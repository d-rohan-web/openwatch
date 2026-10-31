"""All-India power position (demand met + generation mix) from MoP's MERIT India dashboard."""
from __future__ import annotations

import re

from selectolax.lexbor import LexborHTMLParser

from apps.collector.feed import Feed
from packages.contracts.record import record

# The HTML fragment the meritindia.in home page reloads every 30 s.
URL = "https://meritindia.in/Dashboard/BindAllIndiaMap"
# Card title → attr name (MW). Trans-national exchange is the last card and has no <br/> in its title.
FIELDS = {"DEMAND MET": "demand_met_mw", "THERMAL GENERATION": "thermal_mw", "GAS GENERATION": "gas_mw",
          "NUCLEAR GENERATION": "nuclear_mw", "HYDRO GENERATION": "hydro_mw", "RENEWABLE GENERATION": "renewable_mw",
          "STORAGE GENERATION": "storage_mw", "OTHER GENERATION": "other_mw", "TRANS NATIONAL EXCHANGE": "transnational_mw"}


def severity(hz: float | None) -> str:
    if hz is None:
        return "info"
    return "warning" if not 49.8 <= hz <= 50.2 else "advisory" if not 49.90 <= hz <= 50.05 else "info"


def parse(html: str, hz: float | None = None) -> list[dict]:
    mw = {}
    for card in LexborHTMLParser(html).css(".stat-card"):
        title, val = card.css_first(".gen_title_sec"), card.css_first(".counter")
        key = title and FIELDS.get(" ".join(title.text(separator=" ").split()))
        if key and val and (num := re.sub(r"[^\d-]", "", val.text())):
            mw[key] = int(num)
    if "demand_met_mw" not in mw:
        return []
    return [record("all_india", title=f"All-India demand met {mw['demand_met_mw']:,} MW", kind="grid",
                   severity=severity(hz), frequency_hz=hz, link="https://meritindia.in/", **mw)]


async def fetch(ctx) -> list[dict]:
    # ponytail: no live frequency source found (RLDC widgets are frozen/empty); add hz when one turns up
    return parse((await ctx.get(URL, raw_ext="html")).text)


FEED = Feed(id="grid_power", label="Power grid (MERIT India)", section="infrastructure", homepage="https://meritindia.in/",
            terms="Ministry of Power public dashboard (MERIT); no explicit licence stated, attribute MoP / Grid-India",
            every=300, fetch=fetch)
