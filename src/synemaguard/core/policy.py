"""Policy loading and validation.

A policy is a human-readable YAML file (the "swap ethics by config, not code" surface). The
loader validates required fields, **normalizes framework weights to sum to 1.0**, and computes
a ``policy_hash`` (sha256 of the resolved policy) so any run is reconstructable against the
exact rules in effect.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..ethics.aggregator import VALID_STANCES
from .types import Decision

REQUIRED_TOP_LEVEL = ("version", "ethics", "scanners", "circuit_breaker")
VALID_FAIL_MODES = {"BLOCK", "FLAG"}


class PolicyError(ValueError):
    """Raised when a policy file is malformed or missing required fields."""


@dataclass
class FrameworkConfig:
    enabled: bool = True
    weight: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScannerConfig:
    enabled: bool = True
    fail_mode: Decision = Decision.BLOCK
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyConfig:
    version: str
    stance: str
    human_review_on_flag: bool
    frameworks: dict[str, FrameworkConfig]
    scanners: dict[str, ScannerConfig]
    character_bible_ref: str | None
    cumulative_risk_threshold: float
    policy_hash: str
    raw: dict[str, Any] = field(default_factory=dict)


def _require(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise PolicyError(f"missing required field '{key}' in {where}")
    return d[key]


def _compute_hash(resolved: dict[str, Any]) -> str:
    canonical = json.dumps(resolved, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_policy(path: str | Path) -> PolicyConfig:
    """Load and validate a policy YAML file into a :class:`PolicyConfig`."""
    p = Path(path)
    if not p.exists():
        raise PolicyError(f"policy file not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyError(f"malformed YAML in {p}: {exc}") from exc

    if not isinstance(raw, dict):
        raise PolicyError(f"policy must be a mapping, got {type(raw).__name__}")

    for key in REQUIRED_TOP_LEVEL:
        _require(raw, key, "policy root")

    return _build(raw)


def load_policy_from_dict(raw: dict[str, Any]) -> PolicyConfig:
    """Build a :class:`PolicyConfig` from an already-parsed mapping (used in tests)."""
    if not isinstance(raw, dict):
        raise PolicyError("policy must be a mapping")
    for key in REQUIRED_TOP_LEVEL:
        _require(raw, key, "policy root")
    return _build(raw)


def _build(raw: dict[str, Any]) -> PolicyConfig:
    ethics = _require(raw, "ethics", "policy root")
    stance = _require(ethics, "stance", "ethics")
    if stance not in VALID_STANCES:
        raise PolicyError(f"invalid stance '{stance}'; expected one of {VALID_STANCES}")

    # --- frameworks: parse + normalize weights to sum 1.0 over enabled frameworks ----------
    frameworks: dict[str, FrameworkConfig] = {}
    for name, fcfg in (ethics.get("frameworks") or {}).items():
        fcfg = fcfg or {}
        frameworks[name] = FrameworkConfig(
            enabled=bool(fcfg.get("enabled", True)),
            weight=float(fcfg.get("weight", 0.0)),
            params={k: v for k, v in fcfg.items() if k not in ("enabled", "weight")},
        )
    if not frameworks:
        raise PolicyError("ethics.frameworks must define at least one framework")

    enabled_weight = sum(fc.weight for fc in frameworks.values() if fc.enabled)
    if enabled_weight > 0:
        for fc in frameworks.values():
            if fc.enabled:
                fc.weight = fc.weight / enabled_weight
    else:
        # No usable weights — assign equal weight across enabled frameworks.
        enabled = [fc for fc in frameworks.values() if fc.enabled]
        for fc in enabled:
            fc.weight = 1.0 / len(enabled) if enabled else 0.0

    # --- scanners --------------------------------------------------------------------------
    scanners: dict[str, ScannerConfig] = {}
    for name, scfg in (raw.get("scanners") or {}).items():
        scfg = scfg or {}
        fail_mode = str(scfg.get("fail_mode", "BLOCK")).upper()
        if fail_mode not in VALID_FAIL_MODES:
            raise PolicyError(
                f"scanner '{name}' has invalid fail_mode '{fail_mode}'; expected {VALID_FAIL_MODES}"
            )
        scanners[name] = ScannerConfig(
            enabled=bool(scfg.get("enabled", True)),
            fail_mode=Decision[fail_mode],
            params={k: v for k, v in scfg.items() if k not in ("enabled", "fail_mode")},
        )

    cb = _require(raw, "circuit_breaker", "policy root")
    threshold = float(_require(cb, "cumulative_risk_threshold", "circuit_breaker"))

    # Resolve a canonical view for hashing (after normalization, so the hash reflects effect).
    resolved = {
        "version": raw["version"],
        "stance": stance,
        "human_review_on_flag": bool(ethics.get("human_review_on_flag", False)),
        "frameworks": {
            n: {"enabled": f.enabled, "weight": round(f.weight, 6), "params": f.params}
            for n, f in frameworks.items()
        },
        "scanners": {
            n: {"enabled": s.enabled, "fail_mode": s.fail_mode.value, "params": s.params}
            for n, s in scanners.items()
        },
        "character_bible_ref": raw.get("character_bible_ref"),
        "cumulative_risk_threshold": threshold,
    }

    return PolicyConfig(
        version=str(raw["version"]),
        stance=stance,
        human_review_on_flag=bool(ethics.get("human_review_on_flag", False)),
        frameworks=frameworks,
        scanners=scanners,
        character_bible_ref=raw.get("character_bible_ref"),
        cumulative_risk_threshold=threshold,
        policy_hash=_compute_hash(resolved),
        raw=raw,
    )
