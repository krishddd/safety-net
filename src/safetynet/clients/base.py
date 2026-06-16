"""Agent client interface and an offline stub.

An :class:`AgentClient` is a thin transport to an external agent. SafetyNet only needs to send
a prompt and receive text + raw payload; everything safety-related happens in the guard, not here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class AgentRequest:
    prompt: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    text: str
    raw: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AgentClient(Protocol):
    name: str

    def invoke(self, request: AgentRequest) -> AgentResponse:
        ...


class StubAgentClient:
    """Dependency-free client for offline tests/demos.

    By default it echoes the prompt. Pass ``responder`` to simulate an agent that emits unsafe
    content (to exercise the post-stage guard), or ``fixed_response`` for a constant reply.
    """

    name = "stub"

    def __init__(
        self,
        responder: Callable[[str], str] | None = None,
        fixed_response: str | None = None,
    ) -> None:
        self._responder = responder
        self._fixed = fixed_response
        self.calls: list[str] = []  # records prompts seen (handy for asserting "agent not called")

    def invoke(self, request: AgentRequest) -> AgentResponse:
        self.calls.append(request.prompt)
        if self._fixed is not None:
            text = self._fixed
        elif self._responder is not None:
            text = self._responder(request.prompt)
        else:
            text = f"[stub agent] {request.prompt}"
        return AgentResponse(text=text, raw={"stub": True, "prompt": request.prompt})
