"""Clients for the external agents SafetyNet guards.

The generative agents (NeMo Guardrails, LangGraph Server, Dify, CrewAI) run as separate
Docker containers exposing OpenAPI/REST endpoints. SafetyNet never generates content itself —
it calls these endpoints through an :class:`AgentClient` and applies its guardrails around the
call. A dependency-free :class:`StubAgentClient` is provided for offline tests/demos.
"""

from .base import AgentClient, AgentRequest, AgentResponse, StubAgentClient
from .http import HTTPAgentClient, OpenAIChatClient
from .presets import crewai_client, dify_client, langgraph_client, nemo_client

__all__ = [
    "AgentClient",
    "AgentRequest",
    "AgentResponse",
    "StubAgentClient",
    "HTTPAgentClient",
    "OpenAIChatClient",
    "nemo_client",
    "langgraph_client",
    "dify_client",
    "crewai_client",
]
