"""Stance-based combination of framework verdicts — the mechanism SafetyNet is named for.

Stances:
  * ``deontology_veto`` (default): any deontic ``BLOCK`` wins outright; consequentialist scores
    are discarded. This *arrests consequentialism*. Otherwise falls through to ``weighted``.
  * ``weighted``: aggregate safety = weighted mean of per-framework scores (weights normalized
    to sum 1.0); ``Decision = band(mean)``.
  * ``strictest``: the most severe verdict wins. Because lower score == more severe band,
    the most-severe verdict is exactly the minimum-score verdict, so this is both "most severe"
    and "min score" while staying band-consistent.

See docs/ETHICS_ENGINE.md for the worked example.
"""

from __future__ import annotations

from ..core.types import Decision, Verdict

VALID_STANCES = ("deontology_veto", "weighted", "strictest")


def strictest(verdicts: list[Verdict]) -> Verdict:
    """Return the most severe verdict (== minimum safety score), preserving its consistency.

    Re-labels the source to ``aggregate`` while keeping the original decision, score, rationale,
    and deontic flag intact (so a deontic veto's flag propagates to the circuit breaker).
    """
    if not verdicts:
        return Verdict.from_score("aggregate", 1.0, "no verdicts; default allow")
    worst = min(verdicts, key=lambda v: v.score)
    return Verdict(
        source="aggregate",
        decision=worst.decision,
        score=worst.score,
        rationale=f"strictest of {len(verdicts)} verdict(s): {worst.source} — {worst.rationale}",
        deontic=worst.deontic,
    )


class Aggregator:
    """Combines a set of framework verdicts into one node-level ethics verdict."""

    def __init__(self, stance: str = "deontology_veto", weights: dict[str, float] | None = None) -> None:
        if stance not in VALID_STANCES:
            raise ValueError(f"unknown stance {stance!r}; expected one of {VALID_STANCES}")
        self.stance = stance
        self.weights = dict(weights or {})

    def aggregate(self, verdicts: list[Verdict]) -> Verdict:
        if not verdicts:
            return Verdict.from_score("aggregate", 1.0, "no frameworks enabled; default allow")

        if self.stance == "deontology_veto":
            vetoes = [v for v in verdicts if v.deontic and v.decision == Decision.BLOCK]
            if vetoes:
                worst = min(vetoes, key=lambda v: v.score)
                return Verdict(
                    source="aggregate",
                    decision=Decision.BLOCK,
                    score=worst.score,
                    rationale=f"deontological veto — {worst.rationale}",
                    deontic=True,
                )
            return self._weighted(verdicts)

        if self.stance == "weighted":
            return self._weighted(verdicts)

        # strictest
        return strictest(verdicts)

    def _weighted(self, verdicts: list[Verdict]) -> Verdict:
        # Renormalize over the frameworks actually present this round (robust to disabled ones).
        total_w = sum(self.weights.get(v.source, 0.0) for v in verdicts)
        if total_w <= 0:
            # Fall back to equal weights if no weights matched.
            mean = sum(v.score for v in verdicts) / len(verdicts)
            detail = "equal-weight mean (no matching policy weights)"
        else:
            mean = sum(self.weights.get(v.source, 0.0) * v.score for v in verdicts) / total_w
            detail = "weighted mean of " + ", ".join(
                f"{v.source}={v.score:.2f}*w{self.weights.get(v.source, 0.0):.2f}" for v in verdicts
            )
        return Verdict.from_score("aggregate", mean, detail)
