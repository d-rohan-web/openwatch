"""Settings from the environment (.env via docker compose). Keys for keyed feeds are read by the feed itself."""
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATA_DIR = os.getenv("OPENWATCH_DATA_DIR", "./data")
# 0 = keep forever. Records are the dataset; raw source bytes are bulky, so they expire sooner by default.
RETENTION_DAYS = int(os.getenv("OPENWATCH_RETENTION_DAYS", "0"))
RAW_RETENTION_DAYS = int(os.getenv("OPENWATCH_RAW_RETENTION_DAYS", "90"))
# comma separated feed ids to run; empty = all
FEEDS = [f for f in os.getenv("OPENWATCH_FEEDS", "").split(",") if f]
USER_AGENT = os.getenv("OPENWATCH_USER_AGENT", "openwatch/0.1 (open-source India situation map; +https://github.com/rohan-das/openwatch)")
# "india" (default) or "global": what the collector covers; the UI offers the Global view only when global.
SCOPE = os.getenv("OPENWATCH_SCOPE", "india")
# Bulk data access (export zip, archive search). Off until paid access is in place.
EXPORT_ENABLED = os.getenv("OPENWATCH_EXPORT_ENABLED", "false").lower() in ("1", "true", "yes")
