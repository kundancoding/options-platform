"""Cox-Ross-Rubinstein binomial tree pricer (European & American).

Backward-induction on a recombining tree. Suitable for American exercise and
for sanity-checking the closed-form European result.
"""

from __future__ import annotations

from options_platform.pricing.base import OptionContract


def binomial_price(contract: OptionContract, steps: int = 200) -> float:
    """Price an option on a CRR binomial tree with ``steps`` time steps."""
    # TODO: build the tree, walk back applying max(intrinsic, continuation) when
    # contract.exercise_style is American.
    raise NotImplementedError
