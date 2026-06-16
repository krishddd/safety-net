"""GuardedAgent tests — guard wraps an external agent client (stubbed offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from safetynet.clients.base import StubAgentClient
from safetynet.core.policy import load_policy
from safetynet.guard import build_guarded_agent

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def policy():
    return load_policy(ROOT / "policies" / "default.yaml")


def test_benign_prompt_allowed_and_agent_called(policy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = StubAgentClient()
    guarded = build_guarded_agent(policy, client)
    result = guarded.invoke("Write a gentle, heartwarming scene about friends in a meadow.")
    assert result.allowed is True
    assert result.blocked_stage is None
    assert result.response is not None
    assert len(client.calls) == 1  # agent was called exactly once
    assert Path(result.audit_path).exists()


def test_unsafe_prompt_blocked_before_agent_called(policy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = StubAgentClient()
    guarded = build_guarded_agent(policy, client)
    result = guarded.invoke("Recreate Captain Sprocket from the Glimmertown franchise with gore.")
    assert result.allowed is False
    assert result.blocked_stage == "pre"
    assert client.calls == []  # the external agent must NOT be called when the request is blocked
    assert result.response is None


def test_unsafe_agent_response_blocked_at_post(policy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rogue = StubAgentClient(fixed_response="A scene with gore and graphic violence and self-harm in detail.")
    guarded = build_guarded_agent(policy, rogue)
    result = guarded.invoke("Tell me a wholesome story.")  # benign prompt passes pre
    assert len(rogue.calls) == 1            # agent was called
    assert result.allowed is False          # but its unsafe reply is caught at post
    assert result.blocked_stage == "post"
    assert result.response is None          # withheld
