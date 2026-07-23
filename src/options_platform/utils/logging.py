"""Logging configuration using loguru."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def configure_logging(*, level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure stderr logging and, optionally, a rotating file sink."""
    logger.remove()
    logger.add(sys.stderr, level=level.upper())
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(path, level=level.upper(), rotation="10 MB", retention="14 days")


def get_logger(name: str) -> object:
    """Return a logger bound to a module/component name."""
    return logger.bind(component=name)
