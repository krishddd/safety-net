"""Deontological framework — duty/rule based. Some acts are forbidden regardless of outcome.

A breach of any *inviolable* duty yields a hard ``BLOCK`` (``deontic=True``) that the
aggregator's ``deontology_veto`` stance cannot override with a favorable consequentialist
score. This is how SynemaGuard "arrests consequentialism".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.types import Action, Context, Verdict


@dataclass
class Duty:
    """An inviolable duty expressed as forbidden substrings in the action payload.

    Matching is intentionally simple and deterministic for the Phase-1 stub. Real deployments
    swap this for an embedding/LLM-judge check behind the same interface.
    """

    id: str
    description: str
    forbidden_substrings: list[str] = field(default_factory=list)
    block_score: float = 0.10  # safety score reported on violation (lands in the BLOCK band)

    def is_violated(self, action: Action, context: Context) -> bool:
        text = action.payload.lower()
        return any(s.lower() in text for s in self.forbidden_substrings)


class DeontologyFramework:
    """Evaluates an action against a list of inviolable duties."""

    is_deontic = True

    def __init__(self, duties: list[Duty] | None = None, name: str = "deontology") -> None:
        self.name = name
        self.duties: list[Duty] = list(duties or [])

    def evaluate(self, action: Action, context: Context) -> Verdict:
        for duty in self.duties:
            if duty.is_violated(action, context):
                return Verdict.from_score(
                    self.name,
                    duty.block_score,
                    f"violates duty: {duty.id} ({duty.description})",
                    deontic=True,
                )
        return Verdict.from_score(
            self.name,
            0.95,
            "no inviolable duty violated",
            deontic=True,
        )

    @classmethod
    def from_config(cls, cfg: dict, name: str = "deontology") -> DeontologyFramework:
        duties = [
            Duty(
                id=d["id"],
                description=d.get("description", ""),
                forbidden_substrings=d.get("forbidden_substrings", []),
                block_score=d.get("block_score", 0.10),
            )
            for d in cfg.get("duties", [])
        ]
        return cls(duties=duties, name=name)
