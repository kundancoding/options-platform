"""Shared types for the pricing layer.

Defines the canonical :class:`OptionContract` data model and the
:class:`PricingModel` protocol that concrete pricers implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class OptionType(str, Enum):
    """Call or put."""

    CALL = "call"
    PUT = "put"


class ExerciseStyle(str, Enum):
    """Exercise style — European or American."""

    EUROPEAN = "european"
    AMERICAN = "american"


@dataclass(frozen=True)
class OptionContract:
    """Immutable description of a single option contract.

    Parameters
    ----------
    spot:
        Underlying spot price (S).
    strike:
        Strike price (K).
    time_to_expiry:
        Time to expiry in years (T).
    rate:
        Risk-free rate, continuously compounded (r).
    dividend_yield:
        Continuous dividend yield (q).
    volatility:
        Annualized volatility (sigma).
    option_type:
        Call or put.
    exercise_style:
        European (default) or American.
    """

    spot: float
    strike: float
    time_to_expiry: float
    rate: float
    dividend_yield: float
    volatility: float
    option_type: OptionType
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN


class PricingModel(Protocol):
    """Protocol implemented by all pricer entry points."""

    def __call__(self, contract: OptionContract) -> float:  # pragma: no cover
        ...
