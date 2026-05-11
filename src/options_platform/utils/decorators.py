"""Small reusable decorators."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def timed(fn: F) -> F:
    """Log the wall-clock duration of ``fn`` at DEBUG level."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # TODO: time.perf_counter() around the call; log "fn ran in X ms".
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
