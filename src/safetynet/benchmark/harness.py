"""Run scenarios through a SafetyNet gate and score the predictions."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..core.gate import Gate
from ..core.policy import PolicyConfig
from ..core.types import Action, Context, NodeResult, Stage
from ..pipeline import build_ethics_engine, build_scanners
from .types import BenchmarkReport, Scenario, ScenarioResult

logger = logging.getLogger("safetynet.benchmark")


def build_evaluator(
    policy: PolicyConfig, character_bible: dict | None = None
) -> Callable[[str], NodeResult]:
    """Build a single-gate evaluator (ethics + scanners) from a policy."""
    ethics = build_ethics_engine(policy)
    scanners = build_scanners(policy)
    gate = Gate("benchmark", ethics, scanners)
    context = Context(character_bible=character_bible or {}, policy=policy)

    def _evaluate(text: str) -> NodeResult:
        action = Action(node_id="benchmark", kind="generate_script", payload=text)
        return gate.evaluate(action, context, Stage.PRE)

    return _evaluate


def run_benchmark(
    scenarios: list[Scenario],
    policy: PolicyConfig,
    *,
    character_bible: dict | None = None,
    flag_counts_as_unsafe: bool = True,
) -> BenchmarkReport:
    """Evaluate every scenario and produce a :class:`BenchmarkReport`.

    ``flag_counts_as_unsafe`` controls whether a ``FLAG`` is treated as a positive detection
    (default) or only a hard ``BLOCK`` counts. The former measures "did the guard notice",
    the latter "did the guard refuse".
    """
    evaluate = build_evaluator(policy, character_bible)
    results: list[ScenarioResult] = []
    for sc in scenarios:
        node = evaluate(sc.text)
        decision = node.aggregate.decision.value
        predicted_unsafe = decision == "BLOCK" or (flag_counts_as_unsafe and decision == "FLAG")
        results.append(
            ScenarioResult(
                scenario=sc,
                decision=decision,
                score=round(node.aggregate.score, 4),
                predicted_unsafe=predicted_unsafe,
                correct=(predicted_unsafe == sc.expected_unsafe),
                rationale=node.aggregate.rationale,
            )
        )
    logger.info("benchmark complete: %d scenarios", len(results))
    return BenchmarkReport(results=results, flag_counts_as_unsafe=flag_counts_as_unsafe)
