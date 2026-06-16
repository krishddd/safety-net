"""Benchmark data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .metrics import ConfusionMatrix, confusion


@dataclass
class Scenario:
    """A single labeled benchmark item."""

    id: str
    text: str
    expected_unsafe: bool
    source: str = "custom"
    category: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """SafetyNet's prediction for one scenario."""

    scenario: Scenario
    decision: str            # ALLOW | FLAG | BLOCK
    score: float
    predicted_unsafe: bool
    correct: bool
    rationale: str


@dataclass
class BenchmarkReport:
    results: list[ScenarioResult]
    flag_counts_as_unsafe: bool = True

    @property
    def confusion(self) -> ConfusionMatrix:
        return confusion([(r.predicted_unsafe, r.scenario.expected_unsafe) for r in self.results])

    def by_key(self, key: str) -> dict[str, ConfusionMatrix]:
        """Confusion matrices grouped by 'source' or 'category'."""
        groups: dict[str, list[tuple[bool, bool]]] = {}
        for r in self.results:
            k = getattr(r.scenario, key) or "(none)"
            groups.setdefault(k, []).append((r.predicted_unsafe, r.scenario.expected_unsafe))
        return {k: confusion(v) for k, v in sorted(groups.items())}

    def misclassified(self) -> list[ScenarioResult]:
        return [r for r in self.results if not r.correct]

    def summary(self) -> str:
        cm = self.confusion
        lines = [
            f"Scenarios: {cm.total}   (FLAG counts as unsafe: {self.flag_counts_as_unsafe})",
            f"Accuracy {cm.accuracy:.3f} | Precision {cm.precision:.3f} | "
            f"Recall {cm.recall:.3f} | F1 {cm.f1:.3f}",
            f"Confusion: TP={cm.tp} FP={cm.fp} TN={cm.tn} FN={cm.fn}",
        ]
        by_cat = self.by_key("category")
        if len(by_cat) > 1:
            lines.append("By category:")
            for cat, m in by_cat.items():
                lines.append(f"  {cat:<14} acc {m.accuracy:.2f}  (n={m.total})")
        miss = self.misclassified()
        if miss:
            lines.append(f"Misclassified ({len(miss)}):")
            for r in miss[:10]:
                exp = "unsafe" if r.scenario.expected_unsafe else "safe"
                lines.append(f"  [{r.scenario.id}] expected {exp}, got {r.decision} — {r.scenario.text[:50]}")
        return "\n".join(lines)
