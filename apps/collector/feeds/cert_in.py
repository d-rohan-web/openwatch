"""CERT-In advisories (CIAD) and vulnerability notes (CIVN): latest page of each, severity from each note's page."""
from __future__ import annotations

import html
import re
from datetime import datetime, UTC

from apps.collector.feed import Feed
from packages.contracts.record import record

BASE = "https://www.cert-in.org.in/s2cMainServlet"
LISTS = {"advisory": BASE + "?pageid=PUBADVLIST02&year={year}", "vulnerability_note": BASE + "?pageid=VLNLIST02&year={year}"}
SEVERITY = {"LOW": "info", "MEDIUM": "advisory", "HIGH": "warning", "CRITICAL": "critical"}

_notes: dict[str, dict] = {}  # notes don't change once issued; fetch each page once


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _date(s: str) -> datetime:
    return datetime.strptime(re.sub(r"\s+", " ", s), "%B %d, %Y")


def parse_list(page: str) -> list[dict]:
    """[{code, link, date, title}] from a year list page (newest first)."""
    out = []
    for chunk in re.split(r'(?=<a href="/s2cMainServlet\?pageid=PUBVLNOTES0[12]&VLCODE=)', page)[1:]:
        m = re.match(r'<a href="(/s2cMainServlet\?pageid=PUBVLNOTES0[12]&VLCODE=(CI(?:AD|VN)-\d{4}-\d+))"', chunk)
        t = re.search(r"\((\w+ +\d{1,2}, \d{4})\) (.*)", _text(chunk))
        if m and t:
            title = re.split(r"\s*(?:<<\s*)?Previous\b", t[2])[0]  # last entry runs into the pager
            out.append({"code": m[2], "link": "https://www.cert-in.org.in" + m[1], "date": _date(t[1]), "title": title})
    return out


def parse_note(page: str) -> dict:
    """{cert_in_severity, issued, overview} from one advisory / vulnerability note page."""
    t = _text(page.split('id="print_content"', 1)[-1])
    sev = re.search(r"Severity Rating:\s*(\w+)", t)
    issued = re.search(r"Original Issue Date:\s*(\w+ +\d{1,2}, \d{4})", t)
    overview = re.search(r"\bOverview (.*?)(?: Target Audience:| Description |$)", t)
    return {"cert_in_severity": sev and sev[1].upper(), "issued": issued and _date(issued[1]).date().isoformat(),
            "overview": overview and overview[1][:1000]}


def to_record(item: dict, note: dict, type_: str) -> dict:
    return record(item["code"], title=f"{item['code']}: {item['title']}", kind="cyber", observed_at=item["date"],
                  severity=SEVERITY.get(note.get("cert_in_severity") or ""), type=type_, link=item["link"], **note)


async def fetch(ctx) -> list[dict]:
    out = []
    year = datetime.now(UTC).year
    for type_, url in LISTS.items():
        items = parse_list((await ctx.get(url.format(year=year))).text)
        if not items:  # early January: the new year's list is still empty
            items = parse_list((await ctx.get(url.format(year=year - 1))).text)
        for it in items:
            if it["code"] not in _notes:
                _notes[it["code"]] = parse_note((await ctx.get(it["link"])).text)
            out.append(to_record(it, _notes[it["code"]], type_))
    return out


FEED = Feed(id="cert_in", label="Cyber advisories (CERT-In)", section="govt", homepage="https://www.cert-in.org.in/",
            terms="CERT-In public advisories (Government of India, MeitY); see cert-in.org.in terms of use",
            every=3600, fetch=fetch)
