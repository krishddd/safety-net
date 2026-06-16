"""PII / secret scanner tests."""

from __future__ import annotations

from safetynet.core.types import Action, Context, Decision
from safetynet.scanners.pii import PIIScanner


def _scan(text):
    return PIIScanner().scan(Action("n", "generate_text", text), Context())


def test_secret_leakage_blocks():
    assert _scan("here is the key AKIAIOSFODNN7EXAMPLE for access").decision is Decision.BLOCK
    assert _scan("token: sk-abcdefghijklmnopqrstuvwx1234").decision is Decision.BLOCK
    assert _scan("api_key = 'a1b2c3d4e5f6g7h8'").decision is Decision.BLOCK


def test_pii_flags():
    assert _scan("contact me at jane.doe@example.com").decision is Decision.FLAG
    assert _scan("my number is 415-555-2671").decision is Decision.FLAG


def test_valid_credit_card_flags():
    assert _scan("card 4242 4242 4242 4242 expires soon").decision is Decision.FLAG


def test_short_number_not_flagged_as_card():
    # 12 digits is below the 13-19 card range -> not treated as a card; no other PII present.
    assert _scan("order ref 1111 2222 3333 today").decision is Decision.ALLOW


def test_benign_text_allows():
    assert _scan("a gentle story about friends in a meadow").decision is Decision.ALLOW
