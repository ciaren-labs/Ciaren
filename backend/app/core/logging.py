import logging
import sys


def setup_logging(environment: str = "development") -> None:
    level = logging.DEBUG if environment == "development" else logging.INFO
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"

    logging.basicConfig(
        level=level,
        format=fmt,
        stream=sys.stdout,
    )
    # Quiet down noisy third-party loggers
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if environment == "development" else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
