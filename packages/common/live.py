"""Live state shared between collector (writer) and API (reader) through Redis.

  openwatch:feeds          JSON list of feed metadata (written once at collector start)
  openwatch:live:<feed>    JSON list: the feed's current records
  openwatch:health:<feed>  JSON health of the feed
  openwatch:events         pub/sub channel; message = feed id whose live state or health changed
"""
from __future__ import annotations

import json

FEEDS_KEY = "openwatch:feeds"
EVENTS = "openwatch:events"


def live_key(feed: str) -> str:
    return f"openwatch:live:{feed}"


def health_key(feed: str) -> str:
    return f"openwatch:health:{feed}"


def dumps(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str, separators=(",", ":"))
