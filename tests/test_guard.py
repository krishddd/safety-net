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


def test_dify_image_policy_builds_and_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from safetynet.core.policy import load_policy

    img_policy = load_policy(ROOT / "policies" / "dify_image_guard.yaml")
    guarded = build_guarded_agent(img_policy, StubAgentClient())
    # A benign reply with no image -> image_moderation is a no-op; run passes.
    result = guarded.invoke("draw a friendly robot in a meadow")
    assert result.allowed is True


def test_upstream_error_fails_closed(policy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class ExplodingClient:
        name = "boom"

        def invoke(self, request):
            raise RuntimeError("connection refused")

    guarded = build_guarded_agent(policy, ExplodingClient())
    result = guarded.invoke("a perfectly benign prompt")
    assert result.allowed is False          # a failing upstream must not fail open
    assert result.blocked_stage == "upstream"
    assert result.response is None


def test_flag_and_human_review_wiring(policy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # An email triggers the PII scanner's FLAG (not a block): allowed but flagged.
    guarded = build_guarded_agent(policy, StubAgentClient())
    result = guarded.invoke("you can reach me at jane.doe@example.com")
    assert result.allowed is True
    assert result.flagged is True
    assert result.needs_review is False     # default policy has human_review_on_flag: false

    # Flip the policy knob -> the same flag now requests human review.
    policy.human_review_on_flag = True
    guarded2 = build_guarded_agent(policy, StubAgentClient())
    result2 = guarded2.invoke("you can reach me at jane.doe@example.com")
    assert result2.flagged is True and result2.needs_review is True
