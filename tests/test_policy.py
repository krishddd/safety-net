"""Policy loader tests — validation, weight normalization, hashing."""

from __future__ import annotations

from pathlib import Path

import pytest

from synemaguard.core.policy import PolicyError, load_policy, load_policy_from_dict

ROOT = Path(__file__).resolve().parents[1]


def _minimal(**overrides):
    base = {
        "version": "0.1.0",
        "ethics": {
            "stance": "deontology_veto",
            "frameworks": {
                "deontology": {"enabled": True, "weight": 1.0},
                "consequentialism": {"enabled": True, "weight": 3.0},
            },
        },
        "scanners": {"content_safety": {"enabled": True, "fail_mode": "BLOCK"}},
        "circuit_breaker": {"cumulative_risk_threshold": 1.5},
    }
    base.update(overrides)
    return base


def test_loads_default_policy():
    policy = load_policy(ROOT / "policies" / "default.yaml")
    assert policy.version == "0.1.0"
    assert policy.stance == "deontology_veto"
    assert policy.policy_hash  # non-empty
    total = sum(f.weight for f in policy.frameworks.values() if f.enabled)
    assert total == pytest.approx(1.0)


def test_weights_are_normalized():
    policy = load_policy_from_dict(_minimal())
    # 1.0 and 3.0 -> 0.25 and 0.75
    assert policy.frameworks["deontology"].weight == pytest.approx(0.25)
    assert policy.frameworks["consequentialism"].weight == pytest.approx(0.75)


def test_missing_required_field_raises():
    bad = _minimal()
    del bad["circuit_breaker"]
    with pytest.raises(PolicyError):
        load_policy_from_dict(bad)


def test_invalid_stance_raises():
    with pytest.raises(PolicyError):
        load_policy_from_dict(_minimal(ethics={"stance": "utilitarian_only", "frameworks": {"deontology": {"weight": 1.0}}}))


def test_invalid_fail_mode_raises():
    bad = _minimal(scanners={"content_safety": {"enabled": True, "fail_mode": "OPEN"}})
    with pytest.raises(PolicyError):
        load_policy_from_dict(bad)


def test_malformed_yaml_raises(tmp_path):
    p = tmp_path / "broken.yaml"
    p.write_text("version: '0.1.0'\nethics: [this is: not valid", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy(p)
