# SPDX-License-Identifier: AGPL-3.0-only
import json
import logging
import sys

_RESET = "\033[0m"
_LEVEL_COLOR: dict[int, str] = {
    logging.DEBUG: "\033[36m",  # cyan
    logging.INFO: "\033[32m",  # green
    logging.WARNING: "\033[33m",  # yellow
    logging.ERROR: "\033[31m",  # red
    logging.CRITICAL: "\033[1;31m",  # bold red
}


class _ColorFormatter(logging.Formatter):
    """Compact, ANSI-colored log lines for interactive terminal output."""

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLOR.get(record.levelno, "")
        level = f"{color}{record.levelname:<8}{_RESET}"
        # Strip the common "app." package prefix so names stay short.
        name = record.name.removeprefix("app.")
        ts = self.formatTime(record, "%H:%M:%S")
        msg = record.getMessage()
        line = f"{ts} {level} {name}: {msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


_PLAIN_FMT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

# LogRecord attributes that are intrinsic to every record; anything else a caller
# attaches via `extra=` is treated as a structured field and emitted in JSON.
_RESERVED_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


class _JsonFormatter(logging.Formatter):
    """One JSON object per line, for log collectors (Docker/k8s/ELK)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Surface any caller-supplied `extra=` fields as top-level keys.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _resolve_formatter(log_format: str) -> logging.Formatter:
    fmt = log_format.lower()
    if fmt == "json":
        return _JsonFormatter()
    if fmt == "text":
        return logging.Formatter(_PLAIN_FMT)
    # "auto": colorize a real terminal; pipe/redirect gets plain text.
    return _ColorFormatter() if sys.stdout.isatty() else logging.Formatter(_PLAIN_FMT)


def setup_logging(
    environment: str = "development",
    debug: bool = False,
    log_format: str = "auto",
) -> None:
    level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_resolve_formatter(log_format))

    root = logging.getLogger()
    root.setLevel(level)
    # Replace any handlers uvicorn or a previous basicConfig call may have added.
    root.handlers.clear()
    root.addHandler(handler)

    # SQLAlchemy's echo=True writes to sqlalchemy.engine.Engine (the child logger)
    # and sets its level to INFO directly, bypassing any WARNING we put on the
    # parent.  Silence both so SQL never floods the output — echo is removed from
    # the engine creation anyway (see database.py).
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

    # Uvicorn's per-request access log is redundant with our own request tracing;
    # keep the server lifecycle messages (startup / shutdown / errors) visible.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
