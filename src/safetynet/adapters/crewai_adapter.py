"""CrewAI adapter (optional).

Provides a **task guardrail** factory compatible with CrewAI's ``Task(guardrail=...)`` hook,
so a CrewAI agent's output is routed through a SafetyNet gate before it is accepted. CrewAI
guardrails are callables returning ``(success: bool, data)`` — on a SafetyNet ``BLOCK`` the
guardrail fails the task (CrewAI then retries or surfaces the error); otherwise it passes the
output through unchanged.

The import of ``crewai`` is guarded; the guardrail factory itself does **not** require crewai
(it returns a plain callable), so it is unit-testable without the dependency. ``AVAILABLE``
reports whether crewai is importable for the convenience wrappers.

Usage (when crewai is installed)::

    from crewai import Task
    from safetynet.adapters.crewai_adapter import safetynet_guardrail

    task = Task(
        description="Write scene 1",
        agent=script_agent,
        guardrail=safetynet_guardrail(ethics, scanners, node_id="script_agent"),
    )
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ..core.gate import Gate
from ..core.types import Action, Context, Stage
from ..ethics.engine import EthicsEngine

logger = logging.getLogger("safetynet.adapters.crewai")

try:  # pragma: no cover - exercised only when crewai is installed
    import crewai  # noqa: F401

    AVAILABLE = True
except Exception:  # noqa: BLE001
    AVAILABLE = False


def _coerce_text(task_output: Any) -> str:
    """Extract text from a CrewAI TaskOutput (or a plain string) for evaluation."""
    for attr in ("raw", "result", "output"):
        val = getattr(task_output, attr, None)
        if isinstance(val, str):
            return val
    return str(task_output)


def safetynet_guardrail(
    ethics: EthicsEngine,
    scanners=None,
    *,
    node_id: str = "crewai_node",
    kind: str = "generate_text",
) -> Callable[[Any], tuple[bool, Any]]:
    """Return a CrewAI-compatible guardrail callable backed by a SafetyNet gate.

    The callable returns ``(True, output)`` when SafetyNet does not BLOCK, and
    ``(False, reason)`` when it does — CrewAI treats the False case as a guardrail failure.
    """
    gate = Gate(node_id, ethics, scanners or [])

    def _guardrail(task_output: Any) -> tuple[bool, Any]:
        text = _coerce_text(task_output)
        result = gate.evaluate(Action(node_id=node_id, kind=kind, payload=text), Context(), Stage.POST)
        if result.aggregate.decision.value == "BLOCK":
            logger.warning("SafetyNet guardrail blocked %s output: %s", node_id, result.aggregate.rationale)
            return False, f"SafetyNet BLOCK: {result.aggregate.rationale}"
        return True, task_output

    return _guardrail
