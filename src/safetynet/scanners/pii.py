"""PII and secret-leakage scanner (stdlib regex).

Flags personal data (email, phone, SSN, credit card) and — more severely — leaked credentials
(API keys, AWS keys, private keys, bearer tokens). Runs at both gate stages: on the request
(user pasting secrets / PII) and on the response (an agent leaking them). OWASP LLM Top 10:
LLM02 Sensitive Information Disclosure / LLM06.

Detectors are deliberately conservative (credit cards are Luhn-checked) to limit false positives;
swap in Microsoft Presidio or a cloud DLP behind this same scanner interface for production.
"""

from __future__ import annotations

import re

from ..core.types import Action, Context, Verdict

# --- secret/credential detectors (high severity) ------------------------------------------
_SECRET_PATTERNS: dict[str, re.Pattern] = {
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b"),
    "generic_secret": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9._\-/+]{12,}"
    ),
}

# --- PII detectors (medium severity) -------------------------------------------------------
_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "us_ssn": re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}(?!\d)"),
    "ipv4": re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
}

_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    nums = [int(d) for d in digits]
    if not 13 <= len(nums) <= 19:
        return False
    total, parity = 0, len(nums) % 2
    for i, n in enumerate(nums):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _find_cards(text: str) -> list[str]:
    out = []
    for m in _CARD_RE.finditer(text):
        digits = re.sub(r"[ -]", "", m.group(0))
        if _luhn_ok(digits):
            out.append("credit_card")
            break
    return out


class PIIScanner:
    name = "pii"

    def __init__(self, detect_secrets: bool = True, detect_pii: bool = True) -> None:
        self.detect_secrets = detect_secrets
        self.detect_pii = detect_pii

    def scan(self, action: Action, context: Context) -> Verdict:
        text = action.payload
        secrets = [name for name, rx in _SECRET_PATTERNS.items() if rx.search(text)] if self.detect_secrets else []
        if secrets:
            return Verdict.from_score(self.name, 0.08, f"credential/secret leakage: {secrets}")

        pii = []
        if self.detect_pii:
            pii = [name for name, rx in _PII_PATTERNS.items() if rx.search(text)]
            pii += _find_cards(text)
        if pii:
            return Verdict.from_score(self.name, 0.5, f"PII detected: {sorted(set(pii))}")
        return Verdict.from_score(self.name, 0.95, "no PII or secrets detected")
