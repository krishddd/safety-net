"""Framework-agnostic pipeline wiring: nodes + gates + circuit breaker + audit.

The pipeline runs each node through a two-stage gate (pre then post). A halt at any stage stops
the workflow before the next (more expensive / more downstream) node runs — the cascade-risk
mitigation from NetSafe / G-Safeguard.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from .agents.base import Agent
from .core.audit import AuditLogger
from .core.circuit_breaker import CircuitBreaker
from .core.gate import Gate
from .core.policy import PolicyConfig
from .core.types import Action, Context, NodeResult, Stage
from .ethics.aggregator import Aggregator
from .ethics.consequentialism import ConsequentialismFramework
from .ethics.deontology import DeontologyFramework
from .ethics.engine import EthicsEngine
from .scanners.character_bible import CharacterBibleScanner
from .scanners.content_safety import ContentSafetyScanner
from .scanners.copyright import CopyrightScanner
from .scanners.prompt_injection import PromptInjectionScanner

logger = logging.getLogger("safetynet.pipeline")

# Registry mapping policy scanner names to their classes.
SCANNER_REGISTRY = {
    "content_safety": ContentSafetyScanner,
    "copyright": CopyrightScanner,
    "prompt_injection": PromptInjectionScanner,
    "character_bible": CharacterBibleScanner,
}


@dataclass
class RunReport:
    run_id: str
    halted: bool
    halt_reason: str | None
    audit_path: str
    node_results: list[NodeResult] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)


def build_ethics_engine(policy: PolicyConfig) -> EthicsEngine:
    """Construct the ethics engine (frameworks + aggregator) from a policy."""
    frameworks = []
    weights: dict[str, float] = {}
    for name, fc in policy.frameworks.items():
        if not fc.enabled:
            continue
        weights[name] = fc.weight
        if name == "deontology":
            frameworks.append(DeontologyFramework.from_config(fc.params, name=name))
        elif name == "consequentialism":
            frameworks.append(ConsequentialismFramework.from_config(fc.params, name=name))
        else:
            logger.warning("unknown framework '%s' in policy; skipping", name)
    aggregator = Aggregator(stance=policy.stance, weights=weights)
    return EthicsEngine(frameworks, aggregator)


def build_scanners(policy: PolicyConfig) -> list[tuple[Any, Any]]:
    """Construct (scanner, fail_mode) pairs for every enabled scanner in the policy."""
    pairs = []
    for name, sc in policy.scanners.items():
        if not sc.enabled:
            continue
        cls = SCANNER_REGISTRY.get(name)
        if cls is None:
            logger.warning("unknown scanner '%s' in policy; skipping", name)
            continue
        pairs.append((cls(**sc.params), sc.fail_mode))
    return pairs


class Pipeline:
    """A three-node generative media pipeline (script → image → video) guarded by SafetyNet."""

    def __init__(
        self,
        agents: list[Agent],
        ethics: EthicsEngine,
        scanners: list[tuple[Any, Any]],
        policy: PolicyConfig,
        character_bible: dict | None = None,
    ) -> None:
        self.agents = agents
        self.policy = policy
        self.character_bible = character_bible or {}
        self.gates = {a.node_id: Gate(a.node_id, ethics, scanners) for a in agents}

    def run(self, brief: str, run_id: str | None = None) -> RunReport:
        run_id = run_id or uuid.uuid4().hex[:12]
        breaker = CircuitBreaker(self.policy.cumulative_risk_threshold)
        audit = AuditLogger(run_id, self.policy.version, self.policy.policy_hash)
        context = Context(character_bible=self.character_bible, policy=self.policy)
        report = RunReport(run_id=run_id, halted=False, halt_reason=None, audit_path=str(audit.path))

        current_input = brief
        for agent in self.agents:
            gate = self.gates[agent.node_id]

            # --- PRE stage: evaluate the input before the node runs --------------------------
            pre_action = Action(node_id=agent.node_id, kind=agent.kind, payload=current_input)
            pre_result = gate.evaluate(pre_action, context, Stage.PRE)
            context.trace.append(pre_result)
            report.node_results.append(pre_result)
            halt = breaker.observe(pre_result)
            audit.record(pre_result, input_payload=current_input, output_payload=None, breaker_state=breaker.state())
            if halt:
                return self._halted(report, breaker)

            # --- node executes ---------------------------------------------------------------
            output = agent.run(pre_action, context)
            report.outputs[agent.node_id] = output
            output_text = output if isinstance(output, str) else _to_text(output)

            # --- POST stage: evaluate the output ---------------------------------------------
            post_action = Action(node_id=agent.node_id, kind=agent.kind, payload=output_text)
            post_result = gate.evaluate(post_action, context, Stage.POST)
            post_result.output = output
            context.trace.append(post_result)
            report.node_results.append(post_result)
            halt = breaker.observe(post_result)
            audit.record(post_result, input_payload=current_input, output_payload=output, breaker_state=breaker.state())
            if halt:
                return self._halted(report, breaker)

            # Output of this node becomes the brief for the next.
            current_input = output_text

        return report

    @staticmethod
    def _halted(report: RunReport, breaker: CircuitBreaker) -> RunReport:
        report.halted = True
        report.halt_reason = breaker.halt_reason
        logger.warning("pipeline halted: %s", breaker.halt_reason)
        return report


def _to_text(output: Any) -> str:
    if isinstance(output, dict):
        # Surface the prompt + a flat string so downstream/IP scanners see the content.
        return " ".join(str(v) for v in output.values())
    return str(output)


def build_default_pipeline(policy: PolicyConfig, character_bible: dict | None = None) -> Pipeline:
    """Build the standard Script -> Image -> Video pipeline from a policy."""
    from .agents.image_agent import ImageAgent
    from .agents.script_agent import ScriptAgent
    from .agents.video_agent import VideoAgent

    ethics = build_ethics_engine(policy)
    scanners = build_scanners(policy)
    agents = [ScriptAgent(), ImageAgent(), VideoAgent()]
    return Pipeline(agents, ethics, scanners, policy, character_bible)
