"""Indian equity indices (SENSEX, NIFTY 50, NIFTY BANK, India VIX) via Yahoo Finance's chart "spark" endpoint.

BSE (api.bseindia.com) and NSE (nseindia.com/api) both sit behind Akamai and refuse non-browser clients, so we
don't use them. Polled every 5 min; outside 09:15-15:30 IST weekdays fetch serves its cache for up to 30 min.
"""
from __future__ import annotations

import time
from datetime import datetime, time as dtime, timedelta, timezone, UTC

from apps.collector.feed import Feed
from packages.contracts.record import record

IST = timezone(timedelta(hours=5, minutes=30))
SYMBOLS = {"^BSESN": "SENSEX", "^NSEI": "NIFTY 50", "^NSEBANK": "NIFTY BANK", "^INDIAVIX": "INDIA VIX"}
URL = "https://query1.finance.yahoo.com/v8/finance/spark?range=1d&interval=15m&symbols=" + ",".join(SYMBOLS)
CLOSED_EVERY = 1800


def move_severity(change_pct: float) -> str:
    p = abs(change_pct)
    return "warning" if p >= 4 else "advisory" if p >= 2 else "info"


def ticker(id: str, value: float, prev: float, *, unit: str, as_of, market_state: str | None = None,
           decimals: int = 2, **attrs) -> dict:
    """One unlocated economy record in the ticker shape (shared by markets_india, fx_inr, commodities_india)."""
    change = value - prev
    pct = change / prev * 100 if prev else 0.0
    return record(id, title=f"{id} {value:,.{decimals}f} {'▲' if change >= 0 else '▼'}{abs(pct):.2f}%", kind="market",
                  observed_at=as_of, severity=move_severity(pct), value=round(value, 6), change=round(change, 6),
                  change_pct=round(pct, 3), previous=round(prev, 6), unit=unit, as_of=as_of, market_state=market_state, **attrs)


def market_open(now: datetime) -> bool:
    ist = now.astimezone(IST)  # ponytail: weekday clock only; holidays show as "closed" via the stale as_of check
    return ist.weekday() < 5 and dtime(9, 15) <= ist.time() <= dtime(15, 30)


def parse(d: dict, now: datetime) -> list[dict]:
    out = []
    for sym, name in SYMBOLS.items():
        s = d.get(sym)
        closes = [c for c in (s or {}).get("close") or [] if c is not None]
        if not s or not closes or not s.get("chartPreviousClose"):
            continue
        as_of = datetime.fromtimestamp(s["timestamp"][-1], UTC)
        live = market_open(now) and now - as_of < timedelta(minutes=30)
        out.append(ticker(name, float(s.get("fulldayPrice") or closes[-1]), float(s["chartPreviousClose"]),
                          unit="points", currency="INR", as_of=as_of.isoformat(), market_state="open" if live else "closed",
                          symbol=sym))
    return out


_cache: dict = {"t": 0.0, "records": []}


async def fetch(ctx) -> list[dict]:
    now = datetime.now(UTC)
    if not market_open(now) and _cache["records"] and time.monotonic() - _cache["t"] < CLOSED_EVERY:
        return _cache["records"]
    _cache.update(t=time.monotonic(), records=parse((await ctx.get(URL)).json(), now))
    return _cache["records"]


FEED = Feed(id="markets_india", label="Indian markets (indices)", section="economy",
            homepage="https://finance.yahoo.com/quote/%5EBSESN/",
            terms="Unofficial Yahoo Finance endpoint (query1.finance.yahoo.com, no key); index data © BSE/NSE via Yahoo, "
                  "personal/non-commercial use per Yahoo terms, may be delayed",
            every=300, fetch=fetch)
