import logging
import sys

_RESET = "\033[0m"
_LEVEL_COLOR: dict[int, str] = {
    logging.DEBUG:    "\033[36m",    # cyan
    logging.INFO:     "\033[32m",    # green
    logging.WARNING:  "\033[33m",    # yellow
    logging.ERROR:    "\033[31m",    # red
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


def setup_logging(environment: str = "development", debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    # Colorize only when writing to a real terminal; pipe/redirect gets plain text.
    handler.setFormatter(_ColorFormatter() if sys.stdout.isatty() else logging.Formatter(_PLAIN_FMT))

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
