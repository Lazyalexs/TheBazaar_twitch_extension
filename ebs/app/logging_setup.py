from __future__ import annotations

import datetime
import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """Minimal JSON-line formatter. Emits one JSON object per log record.

    Includes timestamp (ISO 8601 UTC), level, logger, message, plus any
    extra fields passed via the ``extra`` kwarg or a LoggerAdapter.
    """

    _STD_ATTRS: frozenset[str] = frozenset(
        {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._STD_ATTRS:
                obj[key] = value
        return json.dumps(obj, ensure_ascii=False, default=str)


def configure_logging(env: str) -> None:
    """Install the JSON-line formatter on the root logger's stderr handler.

    Sets the root logger level to INFO (DEBUG when *env* is not
    ``"production"``).  Pre-existing handlers are removed so repeated
    calls are idempotent.
    """
    level = logging.DEBUG if env != "production" else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any previously installed handlers (idempotent).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
