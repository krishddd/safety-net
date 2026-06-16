"""The orchestrator-level circuit breaker.

State is **in-memory and scoped to a single run** — a fresh breaker is created per pipeline
execution and never persists risk across runs.

Interaction with the ethics engine (the leak this closes): a hard ``BLOCK`` short-circuits the
breaker **immediately and unconditionally** — it halts even if accumulated risk is zero.
Without this, a single bad node could be "outvoted" by several clean ones and slip through,
quietly reintroducing the exact ends-justify-means tradeoff ``deontology_veto`` exists to
arrest. Only ``FLAG``s feed the cumulative risk -> threshold logic.
"""

from __future__ import annotations

import logging

from .types import Decision, NodeResult

logger = logging.getLogger("synemaguard.breaker")


class CircuitBreaker:
    """Accumulates FLAG risk and halts on BLOCK or on crossing the cumulative threshold."""

    def __init__(self, cumulative_risk_threshold: float) -> None:
        self.threshold = float(cumulative_risk_threshold)
        self.cumulative_risk = 0.0
        self.halted = False
        self.halt_reason: str | None = None

    def observe(self, result: NodeResult) -> bool:
        """Update breaker state from a node result. Returns True if the workflow must halt."""
        if self.halted:
            return True

        decision = result.aggregate.decision

        if decision == Decision.BLOCK:
            self.halted = True
            self.halt_reason = (
                "deontological veto (unconditional halt)"
                if result.aggregate.deontic
                else "hard block"
            )
            logger.warning(
                "circuit breaker HALT at %s/%s: %s",
                result.node_id,
                result.stage.value,
                self.halt_reason,
            )
            return True

        if decision == Decision.FLAG:
            risk = 1.0 - result.aggregate.score
            self.cumulative_risk += risk
            logger.info(
                "FLAG at %s/%s adds risk %.2f -> cumulative %.2f / %.2f",
                result.node_id,
                result.stage.value,
                risk,
                self.cumulative_risk,
                self.threshold,
            )
            if self.cumulative_risk >= self.threshold:
                self.halted = True
                self.halt_reason = (
                    f"cumulative FLAG risk {self.cumulative_risk:.2f} >= threshold {self.threshold:.2f}"
                )
                logger.warning("circuit breaker HALT: %s", self.halt_reason)
                return True

        return False

    def state(self) -> dict:
        return {
            "cumulative_risk": round(self.cumulative_risk, 4),
            "threshold": self.threshold,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
        }
