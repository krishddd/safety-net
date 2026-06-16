"""Content-safety scanner (stub).

Swap-in point for LlamaGuard 4 / NeMoGuard-8B / ShieldGemma (see docs/CONCEPTS.md). The stub
flags a small set of unsafe categories by keyword and lowers the safety score per hit.
"""

from __future__ import annotations

from ..core.types import Action, Context, Verdict
from .base import tokenize

# Minimal illustrative lexicon. A real classifier replaces this entirely.
DEFAULT_UNSAFE_TERMS: dict[str, float] = {
    "gore": 0.5,
    "graphic violence": 0.6,
    "decapitation": 0.7,
    "torture": 0.6,
    "explicit": 0.5,
    "self-harm": 0.8,
    "weapon how-to": 0.7,
}


class ContentSafetyScanner:
    name = "content_safety"

    def __init__(self, unsafe_terms: dict[str, float] | None = None) -> None:
        self.unsafe_terms = {k.lower(): float(v) for k, v in (unsafe_terms or DEFAULT_UNSAFE_TERMS).items()}

    def scan(self, action: Action, context: Context) -> Verdict:
        text = action.payload.lower()
        hits = {term: w for term, w in self.unsafe_terms.items() if term in text}
        # Tokens help catch single-word terms cheaply too.
        token_set = set(tokenize(action.payload))
        for term, w in self.unsafe_terms.items():
            if " " not in term and term in token_set:
                hits[term] = w

        if not hits:
            return Verdict.from_score(self.name, 0.95, "no unsafe content terms detected")

        # Safety drops with the strongest hit; multiple hits compound mildly.
        worst = max(hits.values())
        penalty = min(1.0, worst + 0.05 * (len(hits) - 1))
        safety = max(0.0, 1.0 - penalty)
        return Verdict.from_score(
            self.name, safety, f"unsafe content terms: {sorted(hits)}"
        )
