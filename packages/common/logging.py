"""Structured JSON logging: one JSON object per line on stdout (Loki/Alloy pick it up from the container)."""
from __future__ import annotations

import json
import logging
import sys

_STD = set(vars(logging.makeLogRecord({})))  # attributes every LogRecord has; anything else came in via extra=


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        out.update({k: v for k, v in vars(record).items() if k not in _STD and k not in ("message", "asctime", "color_message")})
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):  # uvicorn's own handlers would print plain text
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    logging.getLogger("httpx").setLevel("WARNING")  # one line per request is noise at our poll rates
