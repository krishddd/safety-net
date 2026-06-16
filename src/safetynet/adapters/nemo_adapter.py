"""NeMo Guardrails adapter (optional).

Exposes SafetyNet as a custom action that NVIDIA NeMo Guardrails can call from a Colang flow,
so a NeMo-managed LLM app can delegate its safety decision to SafetyNet's ethics engine +
scanners. The import of ``nemoguardrails`` is guarded: if it is absent, ``AVAILABLE`` is
``False`` and :func:`register_safetynet_action` raises an informative error.

Usage (when nemoguardrails is installed)::

    from nemoguardrails import LLMRails, RailsConfig
    from safetynet.adapters.nemo_adapter import register_safetynet_action

    rails = LLMRails(RailsConfig.from_path("./config"))
    register_safetynet_action(rails, ethics, scanners, node_id="script_agent")

Then in Colang::

    define flow safetynet check
      $result = execute safetynet_check(text=$user_message)
      if $result.decision == "BLOCK"
        bot refuse
"""

from __future__ import annotations

import logging

from ..core.gate import Gate
from ..core.types import Action, Context, Stage
from ..ethics.engine import EthicsEngine

logger = logging.getLogger("safetynet.adapters.nemo")

try:  # pragma: no cover - exercised only when nemoguardrails is installed
    import nemoguardrails  # noqa: F401

    AVAILABLE = True
except Exception:  # noqa: BLE001
    AVAILABLE = False


def make_safetynet_action(ethics: EthicsEngine, scanners=None, node_id: str = "nemo_node", kind: str = "generate_text"):
    """Build an async NeMo action callable that evaluates text through a SafetyNet gate.

    Returns a coroutine ``safetynet_check(text: str) -> dict`` reporting the decision, score,
    and rationale. This does not require nemoguardrails to construct — only to *register*.
    """
    gate = Gate(node_id, ethics, scanners or [])

    async def safetynet_check(text: str, context: dict | None = None) -> dict:
        action = Action(node_id=node_id, kind=kind, payload=text)
        result = gate.evaluate(action, Context(), Stage.PRE)
        return {
            "decision": result.aggregate.decision.value,
            "score": round(result.aggregate.score, 4),
            "rationale": result.aggregate.rationale,
            "allowed": result.aggregate.decision.value != "BLOCK",
        }

    return safetynet_check


def register_safetynet_action(rails, ethics: EthicsEngine, scanners=None, *, node_id: str = "nemo_node", name: str = "safetynet_check") -> None:
    """Register the SafetyNet action on a ``nemoguardrails.LLMRails`` instance."""
    if not AVAILABLE:
        raise ImportError(
            "nemoguardrails is not installed. Install the optional extra: pip install '.[nemo]'"
        )
    action = make_safetynet_action(ethics, scanners, node_id=node_id)
    rails.register_action(action, name=name)
    logger.info("registered NeMo action %r backed by SafetyNet", name)
