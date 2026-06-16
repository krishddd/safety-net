"""The configurable ethical-framework engine — SynemaGuard's differentiator.

Frameworks are pluggable evaluators sharing one interface. The aggregator combines their
verdicts per a configured *stance* (e.g. ``deontology_veto`` lets inviolable duties *arrest*
favorable consequentialist outcomes). See docs/ETHICS_ENGINE.md.
"""

from .aggregator import Aggregator, strictest
from .base import EthicalFramework
from .consequentialism import ConsequentialismFramework
from .deontology import DeontologyFramework, Duty
from .engine import EthicsEngine

__all__ = [
    "EthicalFramework",
    "DeontologyFramework",
    "Duty",
    "ConsequentialismFramework",
    "Aggregator",
    "strictest",
    "EthicsEngine",
]
