"""Ready-made clients for the four supported agent frameworks.

Each returns an :class:`~safetynet.clients.base.AgentClient` pointed at that framework's REST
endpoint as exposed by its official Docker image. Endpoint shapes follow each project's API;
adjust paths/fields if your version differs.
"""

from __future__ import annotations

from .base import AgentRequest
from .http import HTTPAgentClient, OpenAIChatClient


def nemo_client(base_url: str = "http://localhost:8000", model: str = "gpt-3.5-turbo", api_key: str | None = None) -> OpenAIChatClient:
    """NVIDIA NeMo Guardrails server (OpenAI-compatible ``/v1/chat/completions``)."""
    return OpenAIChatClient(base_url=base_url, model=model, api_key=api_key, name="nemo")


def langgraph_client(
    base_url: str = "http://localhost:8123",
    assistant_id: str = "agent",
    path: str = "/runs/wait",
    input_key: str = "messages",
) -> HTTPAgentClient:
    """LangGraph Server. Posts to ``/runs/wait`` and reads the final message content."""

    def build(req: AgentRequest) -> dict:
        return {"assistant_id": assistant_id, "input": {input_key: [{"role": "user", "content": req.prompt}]}}

    def parse(data: dict) -> str:
        msgs = (data or {}).get(input_key) or (data or {}).get("output", {}).get(input_key)
        if isinstance(msgs, list) and msgs:
            last = msgs[-1]
            return last.get("content", str(last)) if isinstance(last, dict) else str(last)
        return str(data)

    return HTTPAgentClient(base_url, path, build, parse, name="langgraph")


def dify_client(base_url: str = "http://localhost", api_key: str | None = None, path: str = "/v1/chat-messages") -> HTTPAgentClient:
    """Dify chat/agent app. Posts to ``/v1/chat-messages`` and reads ``answer``."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def build(req: AgentRequest) -> dict:
        return {"inputs": {}, "query": req.prompt, "response_mode": "blocking", "user": "safetynet"}

    def parse(data: dict) -> str:
        return (data or {}).get("answer") or str(data)

    return HTTPAgentClient(base_url, path, build, parse, headers=headers, name="dify")


def crewai_client(base_url: str = "http://localhost:8001", path: str = "/kickoff", query_key: str = "prompt") -> HTTPAgentClient:
    """CrewAI wrapped in a FastAPI app (CrewAI ships no standalone server).

    Assumes a ``POST {path}`` endpoint that accepts ``{query_key: <prompt>}`` and returns
    ``{"result": <text>}`` — adjust to match your wrapper.
    """

    def build(req: AgentRequest) -> dict:
        return {query_key: req.prompt}

    def parse(data: dict) -> str:
        return (data or {}).get("result") or (data or {}).get("output") or str(data)

    return HTTPAgentClient(base_url, path, build, parse, name="crewai")
