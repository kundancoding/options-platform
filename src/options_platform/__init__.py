"""options_platform — modular options pricing and paper-trading library.

Subpackages:

- :mod:`options_platform.pricing`        — analytic and numerical option pricers.
- :mod:`options_platform.volatility`     — implied / historical vol, surfaces.
- :mod:`options_platform.analytics`      — strategies, P&L, scenarios, risk.
- :mod:`options_platform.trading`        — paper orders, positions, broker sim.
- :mod:`options_platform.data`           — SQLite persistence and market data.
- :mod:`options_platform.visualization`  — Plotly chart builders.
- :mod:`options_platform.utils`          — logging, validators, decorators.
"""

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "pricing",
    "volatility",
    "analytics",
    "trading",
    "data",
    "visualization",
    "utils",
]
