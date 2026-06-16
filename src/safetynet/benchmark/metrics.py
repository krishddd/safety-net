"""Pure-stdlib classification metrics for the benchmark harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfusionMatrix:
    """Binary confusion matrix where 'positive' = predicted unsafe."""

    tp: int = 0  # predicted unsafe, actually unsafe
    fp: int = 0  # predicted unsafe, actually safe   (over-blocking)
    tn: int = 0  # predicted safe, actually safe
    fn: int = 0  # predicted safe, actually unsafe   (missed harm)

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "total": self.total,
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


def confusion(pairs: list[tuple[bool, bool]]) -> ConfusionMatrix:
    """Build a confusion matrix from (predicted_unsafe, actual_unsafe) pairs."""
    cm = ConfusionMatrix()
    for predicted, actual in pairs:
        if predicted and actual:
            cm.tp += 1
        elif predicted and not actual:
            cm.fp += 1
        elif not predicted and not actual:
            cm.tn += 1
        else:
            cm.fn += 1
    return cm
