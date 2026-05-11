"""Logging configuration using loguru."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def configure_logging(
    *,
    level: str = "INFO",
    log_file: Path | None = None,
) -> None:
    """Configure global loguru sinks (stderr + optional rotating file)."""
    # TODO: logger.remove(); logger.add(sys.stderr, level=level); add file sink
    # with rotation/retention if log_file is provided.
    _ = (level, log_file, sys, Path)


def get_logger(name: str) -> object:
    """Return a logger bound to ``name``."""
    return logger.bind(component=name)
