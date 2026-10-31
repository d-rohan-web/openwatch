"""Archive round trip: append → dedupe → query open hour → compact → query Parquet → prune."""
import os
from datetime import datetime, timedelta, UTC

from packages.common.archive import Archive
from packages.contracts.record import record, utcnow


def stamped(r, feed="f"):
    return {**r, "feed": feed, "fetched_at": utcnow(), "raw_sha256": None}


def count(a, **kw):
    con, sql, params = a.query(**kw)
    return con.execute(f"SELECT count(*) FROM ({sql})", params).fetchone()[0]


def test_round_trip(tmp_path):
    a = Archive(str(tmp_path))
    r1 = stamped(record("a", title="A", kind="k", lon=77, lat=28, observed_at=datetime.now(UTC), x=1))
    r2 = stamped(record("b", title="B", kind="k", observed_at=datetime.now(UTC)))
    assert a.append("f", [r1, r2], store_all=False) == 2
    assert a.append("f", [r1], store_all=False) == 0          # unchanged → not stored again
    assert a.append("f", [{**r1, "attrs": {"x": 2}}], store_all=False) == 1
    assert count(a, feeds=["f"]) == 3
    assert count(a, feeds=["f"], bbox=(70, 20, 80, 30)) == 2  # unlocated b drops out
    assert count(a, feeds=["f"], ids=["b"]) == 1

    assert a.compact(now=datetime.now(UTC) + timedelta(hours=1)) == 1  # the hour is now closed
    assert not any(p.endswith(".jsonl") for _, _, fs in os.walk(tmp_path) for p in fs)
    assert count(a, feeds=["f"]) == 3
    con, sql, params = a.query(feeds=["f"], ids=["a"])
    assert [row[-2] for row in con.execute(sql, params).fetchall()] == ['{"x": 1}', '{"x": 2}']  # attrs column


def test_empty_and_prune(tmp_path):
    a = Archive(str(tmp_path))
    assert count(a, feeds=["nothing"]) == 0
    old = tmp_path / "records" / "feed=f" / "date=2020-01-01"
    old.mkdir(parents=True)
    assert a.prune(retention_days=30, raw_retention_days=0) == 1 and not old.exists()
    assert a.prune(retention_days=0, raw_retention_days=0) == 0


def test_raw_dedupe(tmp_path):
    a = Archive(str(tmp_path))
    s1, s2 = a.save_raw("f", b"hello", "txt"), a.save_raw("f", b"hello", "txt")
    assert s1 == s2 and a.raw_path("f", s1).endswith(".txt.gz")


def test_redact(monkeypatch):
    from apps.collector.feed import Feed
    from apps.collector.main import redact
    monkeypatch.setenv("X_KEY", "abcdef123456")
    f = Feed(id="x", label="x", section="air", homepage="", terms="", key="X_KEY", fetch=lambda c: None)
    out = redact("HTTPStatusError: 403 for url 'https://h/api/abcdef123456/y?key=zzz&a=1'", [f])
    assert "abcdef123456" not in out and "zzz" not in out and "a=1" in out


def test_query_rejects_unsafe_feed_ids(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        Archive(str(tmp_path)).query(feeds=["x'; DROP TABLE"])


def test_usage(tmp_path):
    a = Archive(str(tmp_path))
    a.save_raw("f", b"x" * 100, "txt")
    u = a.usage()
    assert u["raw"][1] == 1 and u["raw"][0] > 0 and u["records"] == (0, 0)
