"""The pluggable ethical-framework interface.

A framework maps an :class:`Action` + :class:`Context` to a :class:`Verdict`. It never makes
its own categorical cut independent of its score — the ``Decision`` is always derived from the
score via the shared :func:`band` helper (re-exported here from ``core.types``).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Re-export the shared primitives so frameworks import them from one place.
from ..core.types import Action, Context, Decision, Verdict, band

__all__ = ["EthicalFramework", "Action", "Context", "Decision", "Verdict", "band"]


@runtime_checkable
class EthicalFramework(Protocol):
    """A pluggable moral-reasoning module.

    Attributes:
        name: stable identifier used as the verdict source and as the policy weight key.
        is_deontic: True if this framework may issue *hard vetoes* — a ``BLOCK`` from a
            deontic framework can short-circuit aggregation and the circuit breaker.
    """

    name: str
    is_deontic: bool

    def evaluate(self, action: Action, context: Context) -> Verdict:
        ...
