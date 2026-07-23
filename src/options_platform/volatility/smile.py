"""Volatility-smile fitting (per-expiry slice)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import least_squares


@dataclass
class SmileFit:
    """Parametric fit of a single-expiry vol smile."""

    expiry: pd.Timestamp
    params: dict[str, float]

    def sigma(self, strike: float) -> float:
        """Return the fitted implied vol at ``strike``."""
        model = self.params.get("model")
        if strike <= 0:
            raise ValueError("strike must be positive")
        if model == "poly3":
            center = self.params["center"]
            x = np.log(strike / center)
            return max(1e-8, float(sum(self.params[f"c{i}"] * x**i for i in range(4))))
        if model == "svi":
            x = np.log(strike / self.params["forward"])
            total_variance = self.params["a"] + self.params["b"] * (self.params["rho"] * (x - self.params["m"]) + np.sqrt((x - self.params["m"]) ** 2 + self.params["sigma"] ** 2))
            return float(np.sqrt(max(total_variance / self.params["time_to_expiry"], 1e-12)))
        raise ValueError(f"unsupported smile model: {model!r}")


def fit_smile(slice_: pd.DataFrame, model: str = "svi") -> SmileFit:
    """Fit a smile model to a single-expiry strike-vs-IV slice.

    Parameters
    ----------
    slice_:
        DataFrame with columns ``strike`` and ``implied_vol``.
    model:
        One of ``"svi"``, ``"sabr"``, ``"poly3"``.
    """
    required = {"strike", "implied_vol"}
    if not required.issubset(slice_.columns):
        raise ValueError(f"slice_ must contain {sorted(required)}")
    data = slice_.loc[:, ["strike", "implied_vol"]].dropna().astype(float)
    data = data[(data.strike > 0) & (data.implied_vol > 0)]
    if len(data) < 3:
        raise ValueError("at least three valid strike/volatility points are required")
    expiry = pd.Timestamp(slice_["expiry"].iloc[0]) if "expiry" in slice_ else pd.Timestamp.utcnow()
    time = float(slice_.get("time_to_expiry", pd.Series([1.0])).iloc[0])
    if time <= 0:
        raise ValueError("time_to_expiry must be positive")
    strikes, vols = data.strike.to_numpy(), data.implied_vol.to_numpy()
    if model == "poly3":
        center = float(np.median(strikes))
        coefs = np.polyfit(np.log(strikes / center), vols, min(3, len(data) - 1))[::-1]
        coefs = np.pad(coefs, (0, 4 - len(coefs)))
        return SmileFit(expiry, {"model": model, "center": center, **{f"c{i}": float(c) for i, c in enumerate(coefs)}})
    if model != "svi":
        raise ValueError("model must be 'svi' or 'poly3'")
    forward = float(slice_["forward"].iloc[0]) if "forward" in slice_ else float(slice_.get("spot", pd.Series([np.median(strikes)])).iloc[0])
    x = np.log(strikes / forward)
    observed = vols**2 * time
    def residual(p: np.ndarray) -> np.ndarray:
        a, b, rho, m, sigma = p
        return a + b * (rho * (x - m) + np.sqrt((x - m) ** 2 + sigma**2)) - observed
    result = least_squares(residual, x0=np.array([0.001, 0.1, 0.0, 0.0, 0.1]), bounds=([-1.0, 1e-8, -0.999, -5.0, 1e-8], [5.0, 10.0, 0.999, 5.0, 5.0]))
    a, b, rho, m, sigma = result.x
    return SmileFit(expiry, {"model": model, "forward": forward, "time_to_expiry": time, "a": float(a), "b": float(b), "rho": float(rho), "m": float(m), "sigma": float(sigma)})
