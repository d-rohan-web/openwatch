"""Append-only archive of every record and every raw source response (docs/architecture.md §3).

Layout under DATA_DIR:
  records/feed=<f>/date=<YYYY-MM-DD>/hour=<HH>.jsonl     the open hour, appended by the collector
  records/feed=<f>/date=<YYYY-MM-DD>/hour=<HH>.parquet   closed hours, compacted by the collector
  raw/<feed>/<YYYY-MM-DD>/<sha256>.<ext>.gz             original response bytes, deduped by hash

Only the collector writes; the API reads through query() (DuckDB over Parquet + the open JSONL).
"""
from __future__ import annotations

import glob
import gzip
import re
import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timedelta, UTC

import duckdb

from packages.contracts.record import COLUMNS

log = logging.getLogger(__name__)
FEED_ID = re.compile(r"[a-z0-9_]{1,40}")

# Explicit schema for reading JSONL so an empty or odd file can't change column types.
_JSON_COLUMNS = {"feed": "VARCHAR", "id": "VARCHAR", "observed_at": "VARCHAR", "fetched_at": "VARCHAR",
                 "lon": "DOUBLE", "lat": "DOUBLE", "geometry": "VARCHAR", "kind": "VARCHAR", "severity": "VARCHAR",
                 "title": "VARCHAR", "attrs": "VARCHAR", "raw_sha256": "VARCHAR"}
_SELECT = ("feed, id, observed_at::TIMESTAMPTZ AS observed_at, fetched_at::TIMESTAMPTZ AS fetched_at, lon, lat, "
           "geometry, kind, severity, title, attrs, raw_sha256")


def _hour_path(root: str, feed: str, t: datetime) -> str:
    return os.path.join(root, "records", f"feed={feed}", f"date={t:%Y-%m-%d}", f"hour={t:%H}")


class Archive:
    def __init__(self, root: str):
        self.root = root
        self._last: dict[tuple[str, str], str] = {}  # (feed, id) -> content hash last stored

    # ---------- write side (collector) ----------
    def save_raw(self, feed: str, body: bytes, ext: str) -> str:
        sha = hashlib.sha256(body).hexdigest()
        path = os.path.join(self.root, "raw", feed, f"{datetime.now(UTC):%Y-%m-%d}", f"{sha}.{ext}.gz")
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with gzip.open(path + ".tmp", "wb") as f:
                f.write(body)
            os.replace(path + ".tmp", path)
        return sha

    def raw_path(self, feed: str, sha: str) -> str | None:
        hits = glob.glob(os.path.join(self.root, "raw", glob.escape(feed), "*", f"{glob.escape(sha)}.*.gz"))
        return hits[0] if hits else None

    def append(self, feed: str, records: list[dict], store_all: bool) -> int:
        """Append records to the open hour. Unless store_all, a record is kept only when its content changed.

        Returns how many were written. Change tracking is in memory, so after a restart each id is stored once more.
        """
        rows = []
        for r in records:
            if not store_all:
                body = json.dumps([r["title"], r["severity"], r["lon"], r["lat"], r["geometry"], r["attrs"]],
                                  sort_keys=True, default=str).encode()
                h = hashlib.sha1(body, usedforsecurity=False).hexdigest()  # change detection, not security
                if self._last.get((feed, r["id"])) == h:
                    continue
                self._last[(feed, r["id"])] = h
            row = {c: r.get(c) for c in COLUMNS}
            row["feed"] = feed
            row["geometry"] = json.dumps(r["geometry"]) if r.get("geometry") else None
            row["attrs"] = json.dumps(r.get("attrs") or {}, ensure_ascii=False, default=str)
            rows.append(json.dumps(row, ensure_ascii=False, default=str))
        if rows:
            path = _hour_path(self.root, feed, datetime.now(UTC)) + ".jsonl"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n".join(rows) + "\n")
        return len(rows)

    def compact(self, now: datetime | None = None) -> int:
        """Turn every closed hour's JSONL into Parquet. Safe to run repeatedly; returns files compacted."""
        current = _hour_path(self.root, "x", now or datetime.now(UTC))[-len("date=YYYY-MM-DD/hour=HH"):]
        done = 0
        for path in glob.glob(os.path.join(self.root, "records", "feed=*", "date=*", "hour=*.jsonl")):
            if path[:-len(".jsonl")].endswith(current):
                continue
            out = path[:-len(".jsonl")] + ".parquet"
            con = duckdb.connect()
            if os.path.exists(out):  # a crash between COPY and remove: merge rather than lose either side
                src = f"SELECT * FROM read_parquet(?, hive_partitioning=false) UNION ALL SELECT {_SELECT} FROM read_json(?, format='newline_delimited', columns={_JSON_COLUMNS})"
                params = [out, path]
            else:
                src = f"SELECT {_SELECT} FROM read_json(?, format='newline_delimited', columns={_JSON_COLUMNS})"
                params = [path]
            con.execute(f"COPY ({src}) TO '{out}.tmp' (FORMAT parquet, COMPRESSION zstd)", params)
            con.close()
            os.replace(out + ".tmp", out)
            os.remove(path)
            done += 1
        return done

    def prune(self, retention_days: int, raw_retention_days: int, now: datetime | None = None) -> int:
        """Delete whole days older than the retention (0 = keep forever). Returns directories removed."""
        now = now or datetime.now(UTC)
        removed = 0
        for days, pattern, prefix in ((retention_days, ("records", "feed=*", "date=*"), "date="),
                                      (raw_retention_days, ("raw", "*", "*"), "")):
            if not days:
                continue
            cutoff = f"{now - timedelta(days=days):%Y-%m-%d}"
            for d in glob.glob(os.path.join(self.root, *pattern)):
                if os.path.basename(d).removeprefix(prefix) < cutoff:
                    shutil.rmtree(d)
                    removed += 1
        return removed

    def usage(self) -> dict[str, tuple[int, int]]:
        """{"records"|"raw": (bytes, files)} on disk, for monitoring."""
        out = {}
        for kind in ("records", "raw"):
            size = files = 0
            for dirpath, _, names in os.walk(os.path.join(self.root, kind)):
                for n in names:
                    try:
                        size += os.path.getsize(os.path.join(dirpath, n))
                        files += 1
                    except OSError:
                        pass  # rotated/compacted away mid-walk
            out[kind] = (size, files)
        return out

    # ---------- read side (API, export) ----------
    def query(self, feeds: list[str] | None = None, start: datetime | None = None, end: datetime | None = None,
              bbox: tuple[float, float, float, float] | None = None, ids: list[str] | None = None,
              located_only: bool = False, limit: int | None = None, time_field: str = "fetched"
              ) -> tuple[duckdb.DuckDBPyConnection, str, list]:
        """Build the SQL over the archive. Returns (connection, sql, params) so callers can fetch or COPY it.

        time_field "fetched": when OpenWatch received/stored it (what did we see in this window).
        time_field "observed": when the source says it happened (falls back to fetched_at when missing).
        """
        sources = []
        for f in feeds or []:
            if not FEED_ID.fullmatch(f):  # ids are interpolated into file globs/SQL: never accept anything else
                raise ValueError(f"bad feed id {f!r}")
        for f in feeds or ["*"]:
            base = os.path.join(self.root, "records", f"feed={f}")
            if glob.glob(os.path.join(base, "date=*", "*.parquet")):
                sources.append(f"SELECT * FROM read_parquet('{base}/date=*/*.parquet', union_by_name=true, hive_partitioning=false)")
            if glob.glob(os.path.join(base, "date=*", "*.jsonl")):
                sources.append(f"SELECT {_SELECT} FROM read_json('{base}/date=*/*.jsonl', format='newline_delimited', "
                               f"columns={_JSON_COLUMNS})")
        if not sources:  # nothing stored yet: an empty result with the right columns
            sources = ["SELECT " + ", ".join(f"NULL::{'TIMESTAMPTZ' if c.endswith('_at') else t} AS {c}"
                                             for c, t in _JSON_COLUMNS.items()) + " WHERE false"]
        t = "fetched_at" if time_field == "fetched" else "coalesce(observed_at, fetched_at)"
        where, params = ["true"], []
        if start:
            where.append(f"{t} >= ?"); params.append(start)
        if end:
            where.append(f"{t} < ?"); params.append(end)
        if ids:
            where.append("id IN (" + ",".join("?" * len(ids)) + ")"); params += ids
        if bbox:
            where.append("lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?"); params += [bbox[0], bbox[2], bbox[1], bbox[3]]
        elif located_only:
            where.append("lon IS NOT NULL")
        sql = f"SELECT * FROM ({' UNION ALL '.join(sources)}) WHERE {' AND '.join(where)} ORDER BY {t}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        con = duckdb.connect()
        con.execute("SET TimeZone='UTC'")
        return con, sql, params
