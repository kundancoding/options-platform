"""P&L attribution.

Decomposes a position's mark-to-market P&L into the standard Greek-driven
components (delta, gamma, vega, theta, rho) plus an unexplained residual.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PnLBreakdown:
    """Greek-attributed P&L decomposition between two marks."""

    delta_pnl: float
    gamma_pnl: float
    vega_pnl: float
    theta_pnl: float
    rho_pnl: float
    residual: float

    @property
    def total(self) -> float:
        """Sum of all components (should match the actual P&L delta)."""
        return (
            self.delta_pnl
            + self.gamma_pnl
            + self.vega_pnl
            + self.theta_pnl
            + self.rho_pnl
            + self.residual
        )


def attribute_pnl(
    *,
    prev_mark: float,
    curr_mark: float,
    greeks_prev: object,
    delta_spot: float,
    delta_vol: float,
    delta_t: float,
    delta_rate: float,
) -> PnLBreakdown:
    """Attribute (curr_mark - prev_mark) to the prior-period Greeks."""
    for field in ("delta", "gamma", "vega", "theta", "rho"):
        if not hasattr(greeks_prev, field):
            raise TypeError(f"greeks_prev must expose {field!r}")
    delta_pnl = float(greeks_prev.delta) * delta_spot
    gamma_pnl = 0.5 * float(greeks_prev.gamma) * delta_spot**2
    vega_pnl = float(greeks_prev.vega) * delta_vol
    # theta is calendar-time decay; delta_t is elapsed calendar time in years.
    theta_pnl = float(greeks_prev.theta) * delta_t
    rho_pnl = float(greeks_prev.rho) * delta_rate
    residual = (curr_mark - prev_mark) - (delta_pnl + gamma_pnl + vega_pnl + theta_pnl + rho_pnl)
    return PnLBreakdown(delta_pnl, gamma_pnl, vega_pnl, theta_pnl, rho_pnl, residual)
