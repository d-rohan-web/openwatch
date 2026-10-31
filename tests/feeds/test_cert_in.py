from pathlib import Path

from apps.collector.feeds.cert_in import parse_list, parse_note, to_record

FIX = Path(__file__).parent.parent / "fixtures"


def test_parse():
    items = parse_list((FIX / "cert_in.html").read_text())
    assert [i["code"] for i in items] == ["CIVN-2026-0533", "CIVN-2026-0532", "CIVN-2026-0514"]
    assert items[-1]["title"] == "Multiple Vulnerabilities in Microsoft Products"  # pager trimmed off
    note = parse_note((FIX / "cert_in_note.html").read_text())
    assert note["cert_in_severity"] == "HIGH" and note["issued"] == "2026-10-27"
    assert note["overview"].startswith("A vulnerability has been reported in Radius Xenia")
    r = to_record(items[0], note, "vulnerability_note")
    assert r["kind"] == "cyber" and r["severity"] == "warning" and r["lon"] is None
    assert r["observed_at"] == "2026-10-30T00:00:00+00:00" and r["attrs"]["link"].endswith("VLCODE=CIVN-2026-0533")
