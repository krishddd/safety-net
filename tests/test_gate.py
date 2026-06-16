"""Gate tests — strictest combination and fail-closed posture."""

from __future__ import annotations

from safetynet.core.gate import Gate
from safetynet.core.types import Action, Context, Decision, Stage, Verdict
from safetynet.ethics.aggregator import Aggregator
from safetynet.ethics.engine import EthicsEngine


class AllowFramework:
    name = "allow_fw"
    is_deontic = False

    def evaluate(self, action, context):
        return Verdict.from_score(self.name, 0.95, "fine")


class FlaggingScanner:
    name = "flagger"

    def scan(self, action, context):
        return Verdict.from_score(self.name, 0.4, "suspicious")


class ThrowingScanner:
    name = "boom_scanner"

    def scan(self, action, context):
        raise RuntimeError("scanner exploded")


def _engine():
    return EthicsEngine([AllowFramework()], Aggregator(stance="weighted", weights={"allow_fw": 1.0}))


def _action():
    return Action("script_agent", "generate_script", "some content")


def test_gate_takes_strictest_of_ethics_and_scanners():
    gate = Gate("script_agent", _engine(), [(FlaggingScanner(), Decision.BLOCK)])
    result = gate.evaluate(_action(), Context(), Stage.PRE)
    # ethics allows (0.95) but scanner flags (0.4) -> node decision is the stricter FLAG.
    assert result.aggregate.decision is Decision.FLAG
    assert result.aggregate.score == 0.4


def test_gate_fails_closed_when_scanner_raises():
    gate = Gate("script_agent", _engine(), [(ThrowingScanner(), Decision.BLOCK)])
    result = gate.evaluate(_action(), Context(), Stage.PRE)
    # The throwing scanner must become a BLOCK (fail-closed), never a silent ALLOW.
    assert result.aggregate.decision is Decision.BLOCK
    assert any("fail-closed" in v.rationale for v in result.scanner_verdicts)


def test_gate_fail_mode_can_be_flag():
    gate = Gate("script_agent", _engine(), [(ThrowingScanner(), Decision.FLAG)])
    result = gate.evaluate(_action(), Context(), Stage.PRE)
    assert result.aggregate.decision is Decision.FLAG
