"""EthicsEngine — runs every enabled framework over an action and aggregates the verdicts."""

from __future__ import annotations

import logging

from ..core.types import Action, Context, Verdict
from .aggregator import Aggregator
from .base import EthicalFramework

logger = logging.getLogger("synemaguard.ethics")


class EthicsEngine:
    """Holds the configured frameworks + aggregator and evaluates actions deterministically."""

    def __init__(self, frameworks: list[EthicalFramework], aggregator: Aggregator) -> None:
        self.frameworks = list(frameworks)
        self.aggregator = aggregator

    def evaluate(self, action: Action, context: Context) -> tuple[Verdict, list[Verdict]]:
        """Return (aggregate_verdict, per_framework_verdicts).

        Fail-closed: a framework that raises is treated as a hard ``BLOCK`` rather than being
        silently skipped — a safety net must not open on error.
        """
        verdicts: list[Verdict] = []
        for fw in self.frameworks:
            try:
                v = fw.evaluate(action, context)
            except Exception as exc:  # noqa: BLE001 — deliberate fail-closed catch-all
                logger.exception("framework %r raised; failing closed to BLOCK", getattr(fw, "name", fw))
                v = Verdict.from_score(
                    getattr(fw, "name", "unknown_framework"),
                    0.0,
                    f"framework error (fail-closed): {exc}",
                    deontic=getattr(fw, "is_deontic", False),
                )
            verdicts.append(v)
        aggregate = self.aggregator.aggregate(verdicts)
        return aggregate, verdicts
