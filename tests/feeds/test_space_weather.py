import json
from datetime import datetime, UTC
from pathlib import Path

from apps.collector.feeds.space_weather import alert_records, flare_record, g_scale, kp_record, r_scale

FX = json.loads((Path(__file__).parent.parent / "fixtures" / "space_weather.json").read_text())


def test_space_weather():
    assert [g_scale(k) for k in (4.33, 4.67, 6.67, 7.67, 8.67, 9.0)] == [0, 1, 3, 4, 4, 5]
    assert [r_scale(f) for f in (5.7e-7, 1e-5, 6.4e-5, 2.1e-4, 3e-3)] == [0, 1, 2, 3, 5]

    kp = kp_record(FX["kp"])
    assert kp["kind"] == "kp" and kp["lon"] is None and kp["severity"] == "info"
    flare = flare_record(FX["flare"])
    assert flare["attrs"]["max_class"] == "B5.7" and flare["severity"] == "info"

    alerts = {r["attrs"]["code"] + r["id"][-4:]: r for r in
              alert_records(FX["alerts"], datetime(2026, 10, 11, 1, tzinfo=UTC))}
    k7 = alerts["ALTK07-220"]
    assert k7["severity"] == "warning" and k7["attrs"]["scale"] == "G3" and k7["title"].startswith("ALERT: Geomagnetic K-index of 7")
    assert alerts["SUMXM5-328"]["severity"] == "advisory"  # R2
    assert alerts["WARK045431"]["severity"] == "info"     # valid until Oct 11 0600
    assert not any(k.startswith("WARK07") for k in alerts)  # expired Oct 10 2359


def test_unknown_times_from_swpc_dont_crash():
    from datetime import UTC, datetime

    from apps.collector.feeds.space_weather import alert_records, flare_record
    f = flare_record([{"time_tag": "2026-10-31T08:00:00Z", "begin_time": "2026-10-31T07:52:00Z", "max_time": "Unk",
                       "max_class": "C3.1", "max_xrlong": 3.1e-6}])
    assert f["observed_at"].startswith("2026-10-31T07:52")
    now = datetime(2026, 10, 31, 9, tzinfo=UTC)
    msgs = [{"product_id": "A20F", "issue_datetime": "2026-10-31 08:30:00.000",
             "message": "Serial Number: 1\r\nValid To: Unk\r\n\r\nALERT: Electron flux\r\n"},
            {"product_id": "X", "issue_datetime": "Unk", "message": "Serial Number: 2\n\nALERT: x\n"}]
    out = alert_records(msgs, now)
    assert len(out) == 1 and out[0]["title"] == "ALERT: Electron flux"
