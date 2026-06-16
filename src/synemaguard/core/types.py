"""Foundational types shared across ethics frameworks, scanners, and the orchestration core.

This module is the **single source of truth** for the Decision/score mapping (`band()`).
Both the ethics engine and the scanners import `band()` and `Verdict` from here, so a
categorical `Decision` and a continuous safety `score` can never disagree (a 0.4 is always
FLAG, everywhere). See docs/ETHICS_ENGINE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def clamp01(x: float) -> float:
    """Clamp a value into the closed interval [0.0, 1.0]."""
    return max(0.0, min(1.0, float(x)))


class Decision(Enum):
    """The categorical outcome of an evaluation.

    Ordered by severity (ALLOW < FLAG < BLOCK) via :pyattr:`severity`.
    """

    ALLOW = "ALLOW"
    FLAG = "FLAG"
    BLOCK = "BLOCK"

    @property
    def severity(self) -> int:
        return {Decision.ALLOW: 0, Decision.FLAG: 1, Decision.BLOCK: 2}[self]


# --- Decision <-> score banding: the one and only mapping ---------------------------------
# score is a *safety* score in [0, 1]: 1.0 = fully safe, 0.0 = maximally unsafe.
BLOCK_CEILING = 0.33  # score < 0.33          -> BLOCK
FLAG_CEILING = 0.66   # 0.33 <= score < 0.66  -> FLAG  ; score >= 0.66 -> ALLOW

# Representative score for an emitter that only has categorical intuition.
BAND_MIDPOINT: dict[Decision, float] = {
    Decision.BLOCK: 0.16,
    Decision.FLAG: 0.50,
    Decision.ALLOW: 0.83,
}


def band(score: float) -> Decision:
    """Map a safety score to a Decision. The sole authority for this mapping."""
    s = clamp01(score)
    if s < BLOCK_CEILING:
        return Decision.BLOCK
    if s < FLAG_CEILING:
        return Decision.FLAG
    return Decision.ALLOW


class Stage(Enum):
    """Gate stage. Phase 1 is two-phase; in-execution monitoring is deferred (see ARCHITECTURE.md)."""

    PRE = "pre"
    POST = "post"


@dataclass
class Verdict:
    """A single evaluation result from a framework, scanner, or aggregator.

    Invariant: for verdicts built through :pymeth:`from_score` / :pymeth:`categorical`,
    ``decision == band(score)`` always holds. Do not construct ``Verdict`` directly unless
    you intend to preserve an externally-derived (decision, score) pair (e.g. re-labelling an
    already-consistent verdict in the aggregator).
    """

    source: str
    decision: Decision
    score: float
    rationale: str
    deontic: bool = False  # True if issued by a deontological (hard-veto-capable) framework

    @classmethod
    def from_score(cls, source: str, score: float, rationale: str, *, deontic: bool = False) -> Verdict:
        s = clamp01(score)
        return cls(source=source, decision=band(s), score=s, rationale=rationale, deontic=deontic)

    @classmethod
    def categorical(cls, source: str, decision: Decision, rationale: str, *, deontic: bool = False) -> Verdict:
        return cls(
            source=source,
            decision=decision,
            score=BAND_MIDPOINT[decision],
            rationale=rationale,
            deontic=deontic,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "decision": self.decision.value,
            "score": round(self.score, 4),
            "rationale": self.rationale,
            "deontic": self.deontic,
        }


@dataclass
class Action:
    """What a node is about to do (pre-stage) or has just done (post-stage)."""

    node_id: str          # e.g. "script_agent", "image_agent", "video_agent"
    kind: str             # e.g. "generate_script", "generate_image", "generate_video"
    payload: str          # the text being acted on: the input prompt (pre) or the output (post)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    """Ambient context available to every evaluator: the bible, the policy, and the trace."""

    character_bible: dict[str, Any] = field(default_factory=dict)
    policy: Any = None     # synemaguard.core.policy.PolicyConfig (avoid import cycle)
    trace: list[NodeResult] = field(default_factory=list)


@dataclass
class NodeResult:
    """The combined outcome of evaluating one node at one stage."""

    node_id: str
    stage: Stage
    aggregate: Verdict                 # node-level decision (ethics aggregate + scanners, strictest)
    framework_verdicts: list[Verdict] = field(default_factory=list)
    scanner_verdicts: list[Verdict] = field(default_factory=list)
    output: Any = None                 # node output, only populated at POST stage
