"""Agent client tests — offline stub always works; HTTP clients are import-guarded."""

from __future__ import annotations

import pytest

from safetynet.clients.base import AgentRequest, StubAgentClient


def test_stub_echoes_by_default():
    c = StubAgentClient()
    resp = c.invoke(AgentRequest(prompt="hello"))
    assert "hello" in resp.text
    assert c.calls == ["hello"]


def test_stub_fixed_and_responder():
    fixed = StubAgentClient(fixed_response="FIXED")
    assert fixed.invoke(AgentRequest(prompt="x")).text == "FIXED"

    upper = StubAgentClient(responder=str.upper)
    assert upper.invoke(AgentRequest(prompt="hi")).text == "HI"


def test_http_clients_import_guarded():
    from safetynet.clients.http import OpenAIChatClient

    try:
        import httpx  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError):
            OpenAIChatClient("http://localhost:8000")
        return

    client = OpenAIChatClient("http://localhost:8000/", model="m", api_key="k")
    assert client.name == "openai-compatible"
    body = client._build(AgentRequest(prompt="hi there"))
    assert body == {"model": "m", "messages": [{"role": "user", "content": "hi there"}]}
    assert client._parse({"choices": [{"message": {"content": "ok"}}]}) == "ok"


def test_presets_build_when_httpx_available():
    pytest.importorskip("httpx")
    from safetynet.clients.presets import dify_client, langgraph_client, nemo_client

    assert nemo_client("http://localhost:8000").name == "nemo"
    assert langgraph_client("http://localhost:8123").name == "langgraph"
    assert dify_client("http://localhost").name == "dify"
