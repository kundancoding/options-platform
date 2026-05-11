"""Plotly chart builders.

Every public function returns a ``plotly.graph_objects.Figure`` so callers can
either ``st.plotly_chart(fig)`` (Streamlit) or ``fig.show()`` (notebooks)
without modification.
"""

from options_platform.visualization.greeks_charts import plot_greeks_vs_spot
from options_platform.visualization.payoff import plot_payoff
from options_platform.visualization.portfolio_charts import plot_equity_curve
from options_platform.visualization.vol_charts import plot_smile, plot_surface

__all__ = [
    "plot_greeks_vs_spot",
    "plot_payoff",
    "plot_equity_curve",
    "plot_smile",
    "plot_surface",
]
