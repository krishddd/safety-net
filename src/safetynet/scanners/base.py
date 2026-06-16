"""The scanner interface and shared text helpers.

Scanners share the ethics engine's safety-direction convention: ``score`` in [0, 1] where
1.0 = safe and 0.0 = unsafe, mapped to a Decision by the single ``band()`` helper.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from ..core.types import Action, Context, Verdict, band  # noqa: F401 (band re-exported)

__all__ = ["Scanner", "tokenize", "shingles", "jaccard"]

_WORD_RE = re.compile(r"[a-z0-9']+")


@runtime_checkable
class Scanner(Protocol):
    """A pluggable input/output scanner."""

    name: str

    def scan(self, action: Action, context: Context) -> Verdict:
        ...


def tokenize(text: str) -> list[str]:
    """Lowercase word tokenization (stdlib regex only)."""
    return _WORD_RE.findall(text.lower())


def shingles(tokens: list[str], n: int = 2) -> set[tuple[str, ...]]:
    """Return the set of n-gram shingles for a token list."""
    if n <= 1 or len(tokens) < n:
        return {(t,) for t in tokens}
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity of two sets; 0.0 when both empty."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0
