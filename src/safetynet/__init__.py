"""SafetyNet — a deterministic, rule-based ethical orchestration layer for generative AI agents.

SafetyNet sits *outside* the agents (the "AI Control" paradigm) and intercepts every node
of a generative pipeline (Script Agent -> Image Agent -> Video Agent) with pre/post gates,
a configurable ethics engine, a circuit breaker, and a tamper-evident audit log.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
