"""Moderation-backend tests: keyword default + the injectable-backend seam."""

from __future__ import annotations

import pytest

from safetynet.core.types import Action, Context, Decision
from safetynet.scanners.content_safety import ContentSafetyScanner
from safetynet.scanners.moderation import (
    BACKEND_REGISTRY,
    KeywordBackend,
    ModerationResult,
    build_backend,
)


def _scan(scanner, text):
    return scanner.scan(Action("n", "generate_script", text), Context())


def test_keyword_backend_default_behavior_preserved():
    sc = ContentSafetyScanner()  # defaults to keyword backend
    assert _scan(sc, "a scene full of gore").score < 0.66
    assert _scan(sc, "a gentle sunny meadow").decision is Decision.ALLOW


def test_keyword_backend_classify_directly():
    b = KeywordBackend()
    assert b.classify("torture scene").unsafe_score > 0.5
    assert b.classify("a calm garden").unsafe_score < 0.33


def test_scanner_accepts_injected_backend():
    class FakeGuard:
        name = "fake"

        def classify(self, text):
            unsafe = 0.9 if "bad" in text else 0.0
            return ModerationResult(unsafe_score=unsafe, categories=["test"], detail="fake verdict")

    sc = ContentSafetyScanner(backend=FakeGuard())
    blocked = _scan(sc, "this is bad")
    assert blocked.decision is Decision.BLOCK
    assert "fake" in blocked.rationale
    assert _scan(sc, "this is fine").decision is Decision.ALLOW


def test_build_backend_unknown_raises():
    with pytest.raises(ValueError):
        build_backend("does_not_exist")


def test_registry_exposes_real_backends():
    # The heavy backends are registered (constructing them needs optional extras, not tested here).
    assert set(BACKEND_REGISTRY) >= {"keyword", "transformers", "anthropic"}
