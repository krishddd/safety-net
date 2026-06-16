"""Tracing tests — RecordingTracer captures per-stage spans through a guarded invocation."""

from __future__ import annotations

from pathlib import Path

import pytest

from safetynet.clients.base import StubAgentClient
from safetynet.core.policy import load_policy
from safetynet.core.tracing import NullTracer, RecordingTracer
from safetynet.guard import build_guarded_agent

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def policy():
    return load_policy(ROOT / "policies" / "default.yaml")


def test_default_tracer_is_null(policy):
    guarded = build_guarded_agent(policy, StubAgentClient())
    assert isinstance(guarded.tracer, NullTracer)


def test_recording_tracer_captures_allowed_run(policy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tracer = RecordingTracer()
    guarded = build_guarded_agent(policy, StubAgentClient(), tracer=tracer)
    result = guarded.invoke("a gentle, heartwarming garden scene about friends")

    assert len(tracer.runs) == 1
    assert tracer.runs[0]["run_id"] == result.run_id
    # pre + post for an allowed run.
    assert len(tracer.events) == 2
    assert [e["stage"] for e in tracer.events] == ["pre", "post"]
    assert tracer.summaries[0]["allowed"] is True


def test_recording_tracer_on_pre_block(policy, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tracer = RecordingTracer()
    guarded = build_guarded_agent(policy, StubAgentClient(), tracer=tracer)
    guarded.invoke("Recreate Captain Sprocket from the Glimmertown franchise with gore.")

    # Blocked at the request stage -> exactly one recorded event, summary not allowed.
    assert len(tracer.events) == 1
    assert tracer.events[0]["stage"] == "pre"
    assert tracer.summaries[0]["allowed"] is False
