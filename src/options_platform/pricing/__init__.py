"""Option pricing models.

Public surface re-exports the most common entry points so callers can write::

    from options_platform.pricing import black_scholes_price, compute_greeks
"""

from options_platform.pricing.base import OptionContract, OptionType, PricingModel
from options_platform.pricing.black_scholes import black_scholes_price
from options_platform.pricing.binomial import binomial_price
from options_platform.pricing.monte_carlo import monte_carlo_price
from options_platform.pricing.greeks import compute_greeks

__all__ = [
    "OptionContract",
    "OptionType",
    "PricingModel",
    "black_scholes_price",
    "binomial_price",
    "monte_carlo_price",
    "compute_greeks",
]
