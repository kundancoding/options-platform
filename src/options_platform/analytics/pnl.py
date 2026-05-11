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
    # TODO: implement Taylor-expansion attribution; cross-gamma optional.
    raise NotImplementedError
