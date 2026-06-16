"""The per-node Gate: runs scanners + ethics at the pre and post stages.

Fail-closed posture: if a scanner raises, the gate substitutes a verdict at the scanner's
configured ``fail_mode`` (BLOCK by default, never a silent ALLOW). The node-level decision is
the **strictest** of the ethics aggregate and all scanner verdicts; because the strictest verdict
is the minimum-score one, a deontic veto's flag propagates intact to the circuit breaker.
"""

from __future__ import annotations

import logging

from ..ethics.aggregator import strictest
from ..ethics.engine import EthicsEngine
from ..scanners.base import Scanner
from .types import Action, Context, NodeResult, Stage, Verdict

logger = logging.getLogger("safetynet.gate")


class Gate:
    """Wraps one pipeline node with input/output evaluation."""

    def __init__(
        self,
        node_id: str,
        ethics: EthicsEngine,
        scanners: list[tuple[Scanner, FailMode]] | None = None,
    ) -> None:
        self.node_id = node_id
        self.ethics = ethics
        # Each entry is (scanner, fail_mode_decision).
        self.scanners = scanners or []

    def _run_scanners(self, action: Action, context: Context) -> list[Verdict]:
        verdicts: list[Verdict] = []
        for scanner, fail_mode in self.scanners:
            try:
                verdicts.append(scanner.scan(action, context))
            except Exception as exc:  # noqa: BLE001 — deliberate fail-closed catch-all
                logger.exception(
                    "scanner %r raised; failing closed to %s",
                    getattr(scanner, "name", scanner),
                    fail_mode.value,
                )
                verdicts.append(
                    Verdict.categorical(
                        getattr(scanner, "name", "unknown_scanner"),
                        fail_mode,
                        f"scanner error (fail-closed -> {fail_mode.value}): {exc}",
                    )
                )
        return verdicts

    def evaluate(self, action: Action, context: Context, stage: Stage) -> NodeResult:
        ethics_aggregate, framework_verdicts = self.ethics.evaluate(action, context)
        scanner_verdicts = self._run_scanners(action, context)

        node_aggregate = strictest([ethics_aggregate, *scanner_verdicts])
        return NodeResult(
            node_id=self.node_id,
            stage=stage,
            aggregate=node_aggregate,
            framework_verdicts=framework_verdicts,
            scanner_verdicts=scanner_verdicts,
        )


# Re-exported for type clarity in constructors above.
from .types import Decision as FailMode  # noqa: E402
