"""HTTP agent clients (httpx, optional).

``HTTPAgentClient`` is a generic JSON POST client configured by a request builder and a response
parser, so any REST agent can be wrapped. ``OpenAIChatClient`` is a ready preset for
OpenAI-compatible ``/v1/chat/completions`` endpoints (NeMo Guardrails' server speaks this).

Requires the optional ``[http]`` extra (``pip install '.[http]'``); ``httpx`` is imported lazily
so importing this module never requires it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from .base import AgentRequest, AgentResponse

logger = logging.getLogger("safetynet.clients.http")


class HTTPAgentClient:
    """Generic JSON-over-HTTP agent client."""

    def __init__(
        self,
        base_url: str,
        path: str,
        request_builder: Callable[[AgentRequest], dict],
        response_parser: Callable[[dict], str],
        headers: dict[str, str] | None = None,
        method: str = "POST",
        timeout: float = 60.0,
        name: str = "http",
    ) -> None:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "HTTP agent clients require the optional 'http' extra. Install: pip install '.[http]'"
            ) from exc

        self.name = name
        self._httpx = httpx
        self.base_url = base_url.rstrip("/")
        self.path = path
        self.method = method
        self.headers = headers or {}
        self.timeout = timeout
        self._build = request_builder
        self._parse = response_parser

    def invoke(self, request: AgentRequest) -> AgentResponse:  # pragma: no cover - needs a live server
        url = f"{self.base_url}{self.path}"
        body = self._build(request)
        with self._httpx.Client(timeout=self.timeout) as client:
            resp = client.request(self.method, url, json=body, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
        return AgentResponse(text=self._parse(data), raw=data, metadata={"url": url})


def _openai_request(request: AgentRequest, model: str) -> dict:
    # Forward the full conversation when the caller provides it (preserves multi-turn context);
    # otherwise wrap the single prompt.
    messages = (request.metadata or {}).get("messages")
    if not messages:
        messages = [{"role": "user", "content": request.prompt}]
    return {"model": model, "messages": messages}


def _openai_parse(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return str(data)


class OpenAIChatClient(HTTPAgentClient):
    """Preset for OpenAI-compatible ``/v1/chat/completions`` servers (e.g. NeMo Guardrails)."""

    def __init__(
        self,
        base_url: str,
        model: str = "gpt-3.5-turbo",
        api_key: str | None = None,
        path: str = "/v1/chat/completions",
        timeout: float = 60.0,
        name: str = "openai-compatible",
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        super().__init__(
            base_url=base_url,
            path=path,
            request_builder=lambda req: _openai_request(req, model),
            response_parser=_openai_parse,
            headers=headers,
            timeout=timeout,
            name=name,
        )
