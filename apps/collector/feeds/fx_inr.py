"""INR reference rates for USD, EUR, GBP, JPY, CNY, AED from Frankfurter (ECB euro reference rates, crossed).

FBIL's public endpoint (fbil.org.in/wasdm/refrates/fetch) works but trails by about a week and has no CNY, so we
use Frankfurter. ECB publishes once per working day around 16:00 CET; polling hourly just picks that up.
"""
from __future__ import annotations

from datetime import date, timedelta

from apps.collector.feed import Feed
from apps.collector.feeds.markets_india import ticker

CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CNY", "AED")
API = "https://api.frankfurter.dev/v1/"
AED_PER_USD = 3.6725  # ECB has no AED; the dirham is pegged to the dollar, so AED/INR is derived from USD/INR


def parse(latest: dict, prev: dict) -> list[dict]:
    """latest/prev: Frankfurter responses with base INR (rates = foreign units per 1 INR) → INR per 1 unit."""
    out = []
    for d in (latest, prev):
        if "USD" in d["rates"]:
            d["rates"].setdefault("AED", d["rates"]["USD"] * AED_PER_USD)
    for c in CURRENCIES:
        if c in latest["rates"] and c in prev["rates"]:
            out.append(ticker(f"{c}/INR", 1 / latest["rates"][c], 1 / prev["rates"][c], unit="INR", currency="INR",
                              as_of=latest["date"], decimals=4, base=c, previous_date=prev["date"],
                              derived="USD peg 3.6725" if c == "AED" else None))
    return out


async def fetch(ctx) -> list[dict]:
    latest = (await ctx.get(f"{API}latest?base=INR")).json()
    # previous working day's fixing: the last date in a short window ending the day before
    day = date.fromisoformat(latest["date"])
    series = (await ctx.get(f"{API}{day - timedelta(days=7)}..{day - timedelta(days=1)}?base=INR")).json()
    last = max(series["rates"])
    return parse(latest, {"date": last, "rates": series["rates"][last]})


FEED = Feed(id="fx_inr", label="INR exchange rates (ECB)", section="economy", homepage="https://frankfurter.dev/",
            terms="Frankfurter open API (no key), data from ECB euro foreign exchange reference rates, crossed to INR; "
                  "free reuse with attribution to the ECB. AED derived via its USD peg. Not the official FBIL/RBI "
                  "INR reference rate",
            every=3600, fetch=fetch)
