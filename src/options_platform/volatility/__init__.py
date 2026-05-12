"""Volatility estimation and surface tooling."""

from options_platform.volatility.ewma import (
    DEFAULT_LAMBDA,
    RISKMETRICS_DAILY_LAMBDA,
    RISKMETRICS_MONTHLY_LAMBDA,
    ewma_forecast,
    ewma_variance,
    ewma_volatility,
)
from options_platform.volatility.garch import (
    GarchFit,
    fit_garch,
    garch_forecast,
    garch_volatility,
)
from options_platform.volatility.historical_vol import (
    annualize_vol,
    close_to_close_vol,
    garman_klass_vol,
    log_returns,
    parkinson_vol,
    rolling_realized_vol,
    yang_zhang_vol,
)
from options_platform.volatility.implied_vol import implied_volatility
from options_platform.volatility.regime import (
    RegimeResult,
    absolute_threshold_regimes,
    label_regimes,
    regime_summary,
    rolling_thresholds,
)
from options_platform.volatility.smile import fit_smile
from options_platform.volatility.vol_surface import VolSurface, build_surface

__all__ = [
    "DEFAULT_LAMBDA",
    "RISKMETRICS_DAILY_LAMBDA",
    "RISKMETRICS_MONTHLY_LAMBDA",
    "GarchFit",
    "RegimeResult",
    "VolSurface",
    "absolute_threshold_regimes",
    "annualize_vol",
    "build_surface",
    "close_to_close_vol",
    "ewma_forecast",
    "ewma_variance",
    "ewma_volatility",
    "fit_garch",
    "fit_smile",
    "garch_forecast",
    "garch_volatility",
    "garman_klass_vol",
    "implied_volatility",
    "label_regimes",
    "log_returns",
    "parkinson_vol",
    "regime_summary",
    "rolling_realized_vol",
    "rolling_thresholds",
    "yang_zhang_vol",
]
