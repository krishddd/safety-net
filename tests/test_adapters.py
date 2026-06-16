"""Adapter tests — import-safety + the dependency-free guardrail/action seams."""

from __future__ import annotations

import asyncio

import pytest

from safetynet.adapters import crewai_adapter, langgraph_adapter, nemo_adapter
from safetynet.core.types import Decision
from safetynet.ethics.aggregator import Aggregator
from safetynet.ethics.engine import EthicsEngine
from safetynet.scanners.content_safety import ContentSafetyScanner


def _engine():
    return EthicsEngine([], Aggregator(stance="strictest", weights={}))


def _scanners():
    return [(ContentSafetyScanner(), Decision.BLOCK)]


def test_adapter_modules_expose_available_flag():
    for mod in (langgraph_adapter, nemo_adapter, crewai_adapter):
        assert isinstance(mod.AVAILABLE, bool)


def test_langgraph_build_raises_without_dependency():
    if not langgraph_adapter.AVAILABLE:
        with pytest.raises(ImportError):
            langgraph_adapter.build_state_graph(object())


def test_nemo_register_raises_without_dependency():
    if not nemo_adapter.AVAILABLE:
        with pytest.raises(ImportError):
            nemo_adapter.register_safetynet_action(object(), _engine(), _scanners())


def test_nemo_action_callable_works_without_dependency():
    # make_safetynet_action does not need nemoguardrails — only registration does.
    action = nemo_adapter.make_safetynet_action(_engine(), _scanners(), node_id="t")
    result = asyncio.run(action("a scene full of gore"))
    assert result["decision"] in {"FLAG", "BLOCK"}
    assert result["allowed"] is (result["decision"] != "BLOCK")


def test_crewai_guardrail_blocks_unsafe_output():
    guard = crewai_adapter.safetynet_guardrail(_engine(), _scanners(), node_id="t")
    ok_safe, _ = guard("a gentle sunny meadow")
    assert ok_safe is True
    ok_unsafe, reason = guard("a sequence depicting self-harm in graphic detail")
    assert ok_unsafe is False
    assert "SafetyNet BLOCK" in reason
