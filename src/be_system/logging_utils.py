import logging
import sys
import time
from contextlib import contextmanager
from typing import Iterator


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("be_system")
    logger.setLevel(level.upper())
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def fmt_seconds(value: float) -> str:
    return f"{value:.3f}"


@contextmanager
def timer(name: str, logger: logging.Logger) -> Iterator[None]:
    started_at = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started_at
        logger.info("%s | elapsed=%ss", name, fmt_seconds(elapsed))
