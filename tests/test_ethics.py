"""Ethics engine tests — anchored by the worked example from docs/ETHICS_ENGINE.md."""

from __future__ import annotations

import pytest

from synemaguard.core.types import Action, Context, Decision, Verdict, band
from synemaguard.ethics.aggregator import Aggregator, strictest
from synemaguard.ethics.consequentialism import ConsequentialismFramework
from synemaguard.ethics.deontology import DeontologyFramework, Duty
from synemaguard.ethics.engine import EthicsEngine


def _ctx():
    return Context()


# --- The worked example: the mechanism SynemaGuard is named for ---------------------------

def test_deontology_veto_arrests_favorable_consequentialist_score():
    deon = Verdict.from_score("deontology", 0.10, "violates duty: no_deception_of_minors", deontic=True)
    cons = Verdict.from_score("consequentialism", 0.80, "child is comforted")
    assert deon.decision is Decision.BLOCK
    assert cons.decision is Decision.ALLOW

    agg = Aggregator(stance="deontology_veto", weights={"deontology": 0.5, "consequentialism": 0.5})
    result = agg.aggregate([deon, cons])

    assert result.decision is Decision.BLOCK
    assert result.score == pytest.approx(0.10)
    assert result.deontic is True  # propagates so the breaker can halt unconditionally


def test_same_inputs_flag_under_weighted_stance():
    deon = Verdict.from_score("deontology", 0.10, "duty breach", deontic=True)
    cons = Verdict.from_score("consequentialism", 0.80, "net benefit")
    agg = Aggregator(stance="weighted", weights={"deontology": 0.5, "consequentialism": 0.5})
    result = agg.aggregate([deon, cons])
    assert result.score == pytest.approx(0.45)
    assert result.decision is Decision.FLAG


# --- band() is the single source of truth -------------------------------------------------

@pytest.mark.parametrize(
    "score,expected",
    [(0.0, Decision.BLOCK), (0.32, Decision.BLOCK), (0.33, Decision.FLAG),
     (0.65, Decision.FLAG), (0.66, Decision.ALLOW), (1.0, Decision.ALLOW)],
)
def test_band_boundaries(score, expected):
    assert band(score) is expected


def test_verdict_decision_always_consistent_with_score():
    for s in [0.0, 0.2, 0.33, 0.5, 0.66, 0.9, 1.0]:
        v = Verdict.from_score("x", s, "r")
        assert v.decision is band(v.score)
    for d in Decision:
        v = Verdict.categorical("x", d, "r")
        assert band(v.score) is d


def test_strictest_picks_min_score():
    allow = Verdict.from_score("a", 0.9, "ok")
    flag = Verdict.from_score("b", 0.4, "meh")
    worst = strictest([allow, flag])
    assert worst.decision is Decision.FLAG
    assert worst.score == pytest.approx(0.4)


# --- Frameworks ---------------------------------------------------------------------------

def test_deontology_blocks_on_duty_violation():
    fw = DeontologyFramework([Duty("no_deception_of_minors", "no deceiving kids", ["lies to a child"])])
    v = fw.evaluate(Action("script_agent", "generate_script", "the hero lies to a child"), _ctx())
    assert v.decision is Decision.BLOCK
    assert v.deontic is True


def test_deontology_allows_clean_action():
    fw = DeontologyFramework([Duty("d1", "x", ["forbidden phrase"])])
    v = fw.evaluate(Action("script_agent", "generate_script", "a gentle garden scene"), _ctx())
    assert v.decision is Decision.ALLOW


def test_consequentialism_lowers_safety_on_harm():
    fw = ConsequentialismFramework(harm_terms={"gore": 0.6})
    v = fw.evaluate(Action("image_agent", "generate_image", "gore everywhere"), _ctx())
    assert v.score < 0.66
    clean = fw.evaluate(Action("image_agent", "generate_image", "a sunny meadow"), _ctx())
    assert clean.decision is Decision.ALLOW


def test_engine_fail_closed_on_framework_error():
    class Boom:
        name = "boom"
        is_deontic = False

        def evaluate(self, action, context):
            raise RuntimeError("kaboom")

    engine = EthicsEngine([Boom()], Aggregator(stance="strictest", weights={}))
    aggregate, verdicts = engine.evaluate(Action("n", "k", "p"), _ctx())
    assert aggregate.decision is Decision.BLOCK
    assert "fail-closed" in verdicts[0].rationale
