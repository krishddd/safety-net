"""SafetyNet gateway — guard a prompt, optionally forward to an upstream agent, guard the reply.

Configuration via environment variables:
  POLICY_PATH       path to the policy YAML (default: bundled policies/default.yaml)
  UPSTREAM_TYPE     stub | nemo | openai | langgraph | dify | crewai   (default: stub)
  UPSTREAM_URL      base URL of the agent container (e.g. http://nemo:8000)
  UPSTREAM_MODEL    model name for OpenAI-compatible upstreams
  UPSTREAM_API_KEY  bearer token for the upstream, if needed

Endpoints:
  GET  /health                 liveness + active policy hash + upstream type
  POST /guard                  check-only: evaluate a prompt, return the decision (no forwarding)
  POST /v1/chat/completions    OpenAI-compatible proxy: guard -> forward -> guard
"""

from __future__ import annotations

import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from ..clients.base import StubAgentClient
from ..clients.presets import crewai_client, dify_client, langgraph_client, nemo_client
from ..core.gate import Gate
from ..core.logging_config import configure_logging
from ..core.policy import load_policy
from ..core.types import Action, Context, Stage
from ..guard import GuardedAgent, build_ethics_engine, build_scanners

_DEFAULT_POLICY = Path(__file__).resolve().parents[3] / "policies" / "default.yaml"


def _build_client():
    upstream = os.environ.get("UPSTREAM_TYPE", "stub").lower()
    url = os.environ.get("UPSTREAM_URL", "")
    if upstream == "stub" or not url:
        return StubAgentClient()
    if upstream in ("nemo", "openai"):
        return nemo_client(url, model=os.environ.get("UPSTREAM_MODEL", "gpt-3.5-turbo"), api_key=os.environ.get("UPSTREAM_API_KEY"))
    if upstream == "langgraph":
        return langgraph_client(url, assistant_id=os.environ.get("LANGGRAPH_ASSISTANT", "agent"))
    if upstream == "dify":
        return dify_client(url, api_key=os.environ.get("UPSTREAM_API_KEY"))
    if upstream == "crewai":
        return crewai_client(url)
    raise ValueError(f"unknown UPSTREAM_TYPE: {upstream}")


@lru_cache(maxsize=1)
def _state() -> dict[str, Any]:
    configure_logging(to_file=False)
    policy = load_policy(os.environ.get("POLICY_PATH", str(_DEFAULT_POLICY)))
    ethics = build_ethics_engine(policy)
    scanners = build_scanners(policy)
    client = _build_client()
    guarded = GuardedAgent(client, ethics, scanners, policy)
    check_gate = Gate("check", ethics, scanners)
    return {"policy": policy, "guarded": guarded, "check_gate": check_gate, "client": client}


class GuardRequest(BaseModel):
    prompt: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "safetynet"
    messages: list[ChatMessage]


app = FastAPI(title="SafetyNet Gateway", version="0.1.0")


@app.get("/health")
def health() -> dict:
    st = _state()
    policy = st["policy"]
    return {
        "status": "ok",
        "policy_version": policy.version,
        "policy_hash": policy.policy_hash,
        "upstream": st["client"].name,
    }


@app.post("/guard")
def guard(req: GuardRequest) -> dict:
    """Check-only: evaluate a prompt through the gate (no upstream call)."""
    st = _state()
    result = st["check_gate"].evaluate(Action("check", "generate_text", req.prompt), Context(policy=st["policy"]), Stage.PRE)
    agg = result.aggregate
    return {
        "decision": agg.decision.value,
        "score": round(agg.score, 4),
        "allowed": agg.decision.value != "BLOCK",
        "rationale": agg.rationale,
        "scanner_verdicts": [v.to_dict() for v in result.scanner_verdicts],
        "framework_verdicts": [v.to_dict() for v in result.framework_verdicts],
    }


def _last_user_message(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return messages[-1].content if messages else ""


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest) -> dict:
    """OpenAI-compatible proxy: guard the prompt, forward to upstream, guard the response."""
    st = _state()
    prompt = _last_user_message(req.messages)
    result = st["guarded"].invoke(prompt)

    if result.allowed and result.response is not None:
        content = result.response.text
        finish = "stop"
    else:
        content = f"[SafetyNet blocked at {result.blocked_stage}] {result.halt_reason or 'policy violation'}"
        finish = "content_filter"

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "model": req.model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
        "safetynet": {
            "allowed": result.allowed,
            "blocked_stage": result.blocked_stage,
            "halt_reason": result.halt_reason,
            "run_id": result.run_id,
            "audit_path": result.audit_path,
        },
    }
