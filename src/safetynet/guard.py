"""SafetyNet's security gateway: guard an external agent with pre/post checks.

SafetyNet generates nothing. It wraps an :class:`~safetynet.clients.base.AgentClient` (a Docker
agent's REST endpoint) and, around every call:

1. **pre** — evaluates the incoming prompt (scanners + ethics). A ``BLOCK`` refuses *without
   calling the agent* (no spend, no exposure).
2. calls the external agent over HTTP.
3. **post** — evaluates the agent's response. A ``BLOCK`` withholds the output.

A circuit breaker, JSONL audit log, and optional tracer wrap the whole interaction.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from .clients.base import AgentClient, AgentRequest, AgentResponse
from .core.audit import AuditLogger
from .core.circuit_breaker import CircuitBreaker
from .core.gate import Gate
from .core.policy import PolicyConfig
from .core.tracing import NullTracer, Tracer
from .core.types import Action, Context, NodeResult, Stage
from .ethics.aggregator import Aggregator
from .ethics.consequentialism import ConsequentialismFramework
from .ethics.deontology import DeontologyFramework
from .ethics.engine import EthicsEngine
from .scanners.character_bible import CharacterBibleScanner
from .scanners.content_safety import ContentSafetyScanner
from .scanners.copyright import CopyrightScanner
from .scanners.image_moderation import ImageModerationScanner
from .scanners.prompt_injection import PromptInjectionScanner

logger = logging.getLogger("safetynet.guard")

# Registry mapping policy scanner names to their classes.
SCANNER_REGISTRY = {
    "content_safety": ContentSafetyScanner,
    "copyright": CopyrightScanner,
    "prompt_injection": PromptInjectionScanner,
    "character_bible": CharacterBibleScanner,
    "image_moderation": ImageModerationScanner,
}


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
    return EthicsEngine(frameworks, Aggregator(stance=policy.stance, weights=weights))


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


@dataclass
class GuardResult:
    run_id: str
    allowed: bool
    blocked_stage: str | None = None          # "pre" | "post" | None
    halt_reason: str | None = None
    response: AgentResponse | None = None      # the agent reply, when allowed
    audit_path: str = ""
    node_results: list[NodeResult] = field(default_factory=list)


class GuardedAgent:
    """Wraps one external agent endpoint with SafetyNet's pre/post guardrails."""

    def __init__(
        self,
        client: AgentClient,
        ethics: EthicsEngine,
        scanners: list[tuple[Any, Any]],
        policy: PolicyConfig,
        *,
        node_id: str = "agent",
        kind: str = "generate_text",
        character_bible: dict | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.client = client
        self.policy = policy
        self.node_id = node_id
        self.kind = kind
        self.character_bible = character_bible or {}
        self.gate = Gate(node_id, ethics, scanners)
        self.tracer: Tracer = tracer or NullTracer()

    def invoke(self, prompt: str, metadata: dict | None = None, run_id: str | None = None) -> GuardResult:
        run_id = run_id or uuid.uuid4().hex[:12]
        breaker = CircuitBreaker(self.policy.cumulative_risk_threshold)
        audit = AuditLogger(run_id, self.policy.version, self.policy.policy_hash)
        context = Context(character_bible=self.character_bible, policy=self.policy)
        result = GuardResult(run_id=run_id, allowed=False, audit_path=str(audit.path))
        self.tracer.start_run(run_id, {"policy_version": self.policy.version, "policy_hash": self.policy.policy_hash})

        # --- PRE: guard the request before the external agent is called ----------------------
        pre_action = Action(node_id=self.node_id, kind=self.kind, payload=prompt, metadata=metadata or {})
        pre = self.gate.evaluate(pre_action, context, Stage.PRE)
        context.trace.append(pre)
        result.node_results.append(pre)
        halt = breaker.observe(pre)
        audit.record(pre, input_payload=prompt, output_payload=None, breaker_state=breaker.state())
        self.tracer.record(pre, breaker.state())
        if halt:
            return self._finish(result, breaker, blocked_stage="pre")

        # --- call the external agent ---------------------------------------------------------
        response = self.client.invoke(AgentRequest(prompt=prompt, metadata=metadata or {}))

        # --- POST: guard the agent's response ------------------------------------------------
        post_meta = {"output": response.raw, **(response.metadata or {})}
        post_action = Action(node_id=self.node_id, kind=self.kind, payload=response.text, metadata=post_meta)
        post = self.gate.evaluate(post_action, context, Stage.POST)
        post.output = response
        context.trace.append(post)
        result.node_results.append(post)
        halt = breaker.observe(post)
        audit.record(post, input_payload=prompt, output_payload=response.text, breaker_state=breaker.state())
        self.tracer.record(post, breaker.state())
        if halt:
            return self._finish(result, breaker, blocked_stage="post")

        result.response = response
        return self._finish(result, breaker, blocked_stage=None)

    def _finish(self, result: GuardResult, breaker: CircuitBreaker, *, blocked_stage: str | None) -> GuardResult:
        result.allowed = blocked_stage is None
        result.blocked_stage = blocked_stage
        result.halt_reason = breaker.halt_reason
        if blocked_stage:
            logger.warning("SafetyNet blocked at %s stage: %s", blocked_stage, breaker.halt_reason)
        self.tracer.end_run({"allowed": result.allowed, "blocked_stage": blocked_stage, "halt_reason": result.halt_reason})
        return result


def build_guarded_agent(
    policy: PolicyConfig,
    client: AgentClient,
    *,
    node_id: str = "agent",
    kind: str = "generate_text",
    character_bible: dict | None = None,
    tracer: Tracer | None = None,
) -> GuardedAgent:
    """Build a :class:`GuardedAgent` around an external agent client from a policy."""
    ethics = build_ethics_engine(policy)
    scanners = build_scanners(policy)
    return GuardedAgent(
        client, ethics, scanners, policy,
        node_id=node_id, kind=kind, character_bible=character_bible, tracer=tracer,
    )
