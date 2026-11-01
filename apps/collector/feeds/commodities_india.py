"""Gold and silver (IBJA daily benchmark rates, INR) and Brent crude (USD/bbl, Yahoo Finance).

MCX (mcxindia.com) answers 403 from Akamai, and PPAC's Indian-basket price is monthly with downloads behind a
CAPTCHA, so neither is used. IBJA's home page carries its recent closing rates as JSON in hidden inputs.
"""
from __future__ import annotations

import json
from datetime import datetime, UTC

from selectolax.lexbor import LexborHTMLParser

from apps.collector.feed import Feed
from apps.collector.feeds.markets_india import ticker

IBJA = "https://ibjarates.com/"
BRENT = "https://query1.finance.yahoo.com/v8/finance/spark?range=1d&interval=1d&symbols=BZ%3DF"
# hidden input id → (series key, record id, unit)
SERIES = {"HdnGold": ("purity999", "GOLD 999", "INR/10g"), "HdnSilver": ("silverRate", "SILVER 999", "INR/kg")}


def _date(dmy: str) -> str:
    return datetime.strptime(dmy, "%d/%m/%Y").date().isoformat()


def parse_ibja(html: str) -> list[dict]:
    doc, out = LexborHTMLParser(html), []
    for hid, (key, name, unit) in SERIES.items():
        node = doc.css_first(f"#{hid}")
        d = json.loads(node.attributes.get("value") or "{}") if node else {}
        vals, days = d.get(key) or [], d.get("labels") or []
        if len(vals) >= 2 and len(days) == len(vals):
            out.append(ticker(name, float(vals[-1]), float(vals[-2]), unit=unit, currency="INR", as_of=_date(days[-1]),
                              decimals=0, previous_date=_date(days[-2]), source="IBJA"))
    return out


def parse_brent(d: dict) -> list[dict]:
    s = d.get("BZ=F") or {}
    price, prev = s.get("fulldayPrice"), s.get("chartPreviousClose")
    if not price or not prev:
        return []
    ts = s.get("timestamp") or []  # empty while the market is closed (weekends); the last price still stands
    as_of = datetime.fromtimestamp(ts[-1], UTC).isoformat() if ts else None
    return [ticker("BRENT", float(price), float(prev), unit="USD/bbl", currency="USD", as_of=as_of, source="Yahoo Finance (ICE Brent futures)")]


async def fetch(ctx) -> list[dict]:
    gold = parse_ibja((await ctx.get(IBJA, raw_ext="html")).text)
    for r in gold:
        r["raw_sha256"] = ctx.raw_sha
    return gold + parse_brent((await ctx.get(BRENT)).json())


FEED = Feed(id="commodities_india", label="Gold, silver, crude", section="economy", homepage="https://ibjarates.com/",
            terms="IBJA public rates page (ibjarates.com; IBJA also sells an official API; no redistribution licence "
                  "stated, attribute IBJA). Brent via unofficial Yahoo Finance endpoint, personal/non-commercial use",
            every=3600, fetch=fetch)
