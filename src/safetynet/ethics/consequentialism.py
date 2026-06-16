"""Consequentialist framework — weighs expected harm vs benefit of an action's outcome.

Produces a single safety ``score = 1 - net_harm``; the ``Decision`` is derived from that score
by the shared ``band()`` helper. ``harm_threshold`` is an *internal harm-model knob* shaping how
net harm is computed — it is **not** a second, independent decision boundary.
"""

from __future__ import annotations

from ..core.types import Action, Context, Verdict, clamp01


class ConsequentialismFramework:
    """Estimates net harm from weighted harm/benefit signals present in the action payload."""

    is_deontic = False

    def __init__(
        self,
        harm_terms: dict[str, float] | None = None,
        benefit_terms: dict[str, float] | None = None,
        baseline_harm: float = 0.0,
        harm_threshold: float = 0.5,
        name: str = "consequentialism",
    ) -> None:
        self.name = name
        self.harm_terms = {k.lower(): float(v) for k, v in (harm_terms or {}).items()}
        self.benefit_terms = {k.lower(): float(v) for k, v in (benefit_terms or {}).items()}
        self.baseline_harm = float(baseline_harm)
        # Internal modeling knob: scales how strongly aggregate harm signals translate to net
        # harm. Higher threshold => the model tolerates more raw harm before net harm saturates.
        # It never decides BLOCK/FLAG/ALLOW by itself; band() does that from the final score.
        self.harm_threshold = max(1e-6, float(harm_threshold))

    def evaluate(self, action: Action, context: Context) -> Verdict:
        text = action.payload.lower()
        harm = self.baseline_harm + sum(w for term, w in self.harm_terms.items() if term in text)
        benefit = sum(w for term, w in self.benefit_terms.items() if term in text)

        # net harm in [0, 1], shaped (not gated) by harm_threshold.
        raw = max(0.0, harm - benefit)
        net_harm = clamp01(raw / (raw + self.harm_threshold)) if raw > 0 else 0.0
        safety = clamp01(1.0 - net_harm)

        rationale = (
            f"net-harm model: harm={harm:.2f}, benefit={benefit:.2f}, "
            f"net_harm={net_harm:.2f} -> safety={safety:.2f}"
        )
        return Verdict.from_score(self.name, safety, rationale)

    @classmethod
    def from_config(cls, cfg: dict, name: str = "consequentialism") -> ConsequentialismFramework:
        return cls(
            harm_terms=cfg.get("harm_terms", {}),
            benefit_terms=cfg.get("benefit_terms", {}),
            baseline_harm=cfg.get("baseline_harm", 0.0),
            harm_threshold=cfg.get("harm_threshold", 0.5),
            name=name,
        )
