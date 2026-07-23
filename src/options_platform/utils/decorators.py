"""Small reusable decorators."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from time import perf_counter
from typing import Any, TypeVar

from options_platform.utils.logging import get_logger

F = TypeVar("F", bound=Callable[..., Any])


def timed(fn: F) -> F:
    """Log the wall-clock duration of ``fn`` at DEBUG level."""
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            get_logger(__name__).debug("{name} ran in {elapsed:.2f} ms", name=fn.__name__, elapsed=(perf_counter() - started) * 1000)
    return wrapper  # type: ignore[return-value]
