"""Circuit breaker tests — BLOCK short-circuits; FLAGs accumulate to a threshold."""

from __future__ import annotations

from synemaguard.core.circuit_breaker import CircuitBreaker
from synemaguard.core.types import NodeResult, Stage, Verdict


def _result(decision_score: float, *, deontic: bool = False) -> NodeResult:
    agg = Verdict.from_score("aggregate", decision_score, "test", deontic=deontic)
    return NodeResult(node_id="n", stage=Stage.PRE, aggregate=agg)


def test_single_block_halts_with_zero_accumulated_risk():
    cb = CircuitBreaker(cumulative_risk_threshold=1.5)
    halt = cb.observe(_result(0.10, deontic=True))  # BLOCK band, deontic veto
    assert halt is True
    assert cb.halted is True
    assert cb.cumulative_risk == 0.0  # never accrued anything; halted unconditionally
    assert "veto" in cb.halt_reason


def test_non_deontic_block_also_halts_immediately():
    cb = CircuitBreaker(cumulative_risk_threshold=1.5)
    assert cb.observe(_result(0.10, deontic=False)) is True
    assert cb.halt_reason == "hard block"


def test_flags_accumulate_until_threshold():
    cb = CircuitBreaker(cumulative_risk_threshold=1.5)
    # Each FLAG with score 0.5 adds risk 0.5. Need 3 to reach 1.5.
    assert cb.observe(_result(0.5)) is False
    assert cb.observe(_result(0.5)) is False
    assert cb.observe(_result(0.5)) is True
    assert cb.halted is True
    assert "cumulative" in cb.halt_reason


def test_allow_never_accrues_risk():
    cb = CircuitBreaker(cumulative_risk_threshold=1.0)
    for _ in range(5):
        assert cb.observe(_result(0.9)) is False
    assert cb.cumulative_risk == 0.0
    assert cb.halted is False
