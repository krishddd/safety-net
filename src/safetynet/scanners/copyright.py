"""Copyright / IP scanner (stub).

Swap-in point for the GoG pipeline (arXiv:2503.16171) embedding similarity check and the
CopyJudge LVLM judge (arXiv:2502.15278). The stub uses a **faked similarity check** — a
stdlib token-shingle Jaccard against a list of protected terms/titles — with **no embedding
library and no numpy**, honoring the lean-dependency goal.
"""

from __future__ import annotations

from ..core.types import Action, Context, Verdict
from .base import jaccard, shingles, tokenize

# Invented placeholder IP only — never a real trademark — so example/test fixtures stay clean.
DEFAULT_PROTECTED_TERMS: list[str] = [
    "captain sprocket",
    "glimmertown",
    "the glimmertown franchise",
    "moonberry knights",
]


class CopyrightScanner:
    name = "copyright"

    def __init__(self, protected_terms: list[str] | None = None, threshold: float = 0.18) -> None:
        self.protected_terms = [t.lower() for t in (protected_terms or DEFAULT_PROTECTED_TERMS)]
        self.threshold = threshold
        self._protected_shingles = [shingles(tokenize(t), n=2) for t in self.protected_terms]

    def scan(self, action: Action, context: Context) -> Verdict:
        text = action.payload.lower()

        # 1) Exact protected-name mention is an unambiguous high-risk hit.
        named = [t for t in self.protected_terms if t in text]
        if named:
            return Verdict.from_score(
                self.name, 0.08, f"protected IP named verbatim: {named}"
            )

        # 2) Faked similarity: max shingle-Jaccard against any protected term.
        payload_sh = shingles(tokenize(action.payload), n=2)
        best = 0.0
        best_term = None
        for term, sh in zip(self.protected_terms, self._protected_shingles, strict=True):
            sim = jaccard(payload_sh, sh)
            if sim > best:
                best, best_term = sim, term

        if best >= self.threshold:
            safety = max(0.0, 0.5 - best)  # higher similarity -> lower safety
            return Verdict.from_score(
                self.name, safety, f"high IP similarity ({best:.2f}) to '{best_term}'"
            )
        return Verdict.from_score(self.name, 0.95, f"no protected-IP overlap (max sim {best:.2f})")
