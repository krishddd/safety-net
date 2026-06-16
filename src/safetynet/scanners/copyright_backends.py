"""Pluggable detection backends for the copyright/IP scanner.

A backend takes prompt text plus a list of protected works and returns an infringement
``risk`` in [0, 1] (1.0 = clearly infringing). The :class:`CopyrightScanner` converts that to
the project-wide *safety* score in one place.

Backends:
  * :class:`JaccardBackend` — dependency-free default: verbatim-name match + token-shingle
    Jaccard similarity (the Phase-1 stub behavior). Always available.
  * :class:`EmbeddingCopyrightBackend` — GoG-style (arXiv:2503.16171) embedding similarity via
    ``sentence-transformers``. Optional extra ``[embeddings]``; lazy import; fail-closed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .base import jaccard, shingles, tokenize

logger = logging.getLogger("safetynet.scanners.copyright_backends")

# Invented placeholder IP only — never a real trademark — so example/test fixtures stay clean.
DEFAULT_PROTECTED_TERMS: list[str] = [
    "captain sprocket",
    "glimmertown",
    "the glimmertown franchise",
    "moonberry knights",
]


@dataclass
class CopyrightResult:
    risk: float
    matched: str | None = None
    detail: str = ""
    extra: dict = field(default_factory=dict)


@runtime_checkable
class CopyrightBackend(Protocol):
    name: str

    def detect(self, text: str) -> CopyrightResult:
        ...


class JaccardBackend:
    """Verbatim-name + token-shingle Jaccard similarity. The dependency-free default."""

    name = "jaccard"

    def __init__(self, protected_terms: list[str] | None = None, threshold: float = 0.18) -> None:
        self.protected_terms = [t.lower() for t in (protected_terms or DEFAULT_PROTECTED_TERMS)]
        self.threshold = threshold
        self._protected_shingles = [shingles(tokenize(t), n=2) for t in self.protected_terms]

    def detect(self, text: str) -> CopyrightResult:
        low = text.lower()
        named = [t for t in self.protected_terms if t in low]
        if named:
            return CopyrightResult(risk=0.92, matched=named[0], detail=f"protected IP named verbatim: {named}")

        payload_sh = shingles(tokenize(text), n=2)
        best, best_term = 0.0, None
        for term, sh in zip(self.protected_terms, self._protected_shingles, strict=True):
            sim = jaccard(payload_sh, sh)
            if sim > best:
                best, best_term = sim, term
        if best >= self.threshold:
            return CopyrightResult(
                risk=min(1.0, 0.5 + best), matched=best_term,
                detail=f"high IP similarity ({best:.2f}) to '{best_term}'",
            )
        return CopyrightResult(risk=0.05, detail=f"no protected-IP overlap (max sim {best:.2f})")


# GoG uses short descriptive embeddings of protected works; supply real descriptions in config.
DEFAULT_PROTECTED_WORKS: list[str] = [
    "Captain Sprocket, a clockwork robot hero from the Glimmertown animated franchise",
    "The Moonberry Knights, a team of berry-themed cartoon warriors",
]


class EmbeddingCopyrightBackend:
    """GoG-style detection module: cosine similarity of prompt vs protected-work embeddings.

    Optional: requires ``pip install '.[embeddings]'`` (sentence-transformers). Construction
    loads the model and pre-embeds the protected works; the scanner wraps :meth:`detect` in a
    fail-closed handler.
    """

    name = "embedding"

    def __init__(
        self,
        protected_works: list[str] | None = None,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        threshold: float = 0.6,
        protected_terms: list[str] | None = None,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "EmbeddingCopyrightBackend requires the optional 'embeddings' extra. "
                "Install with: pip install '.[embeddings]'"
            ) from exc

        self._util = util
        self.threshold = threshold
        self.protected_works = protected_works or DEFAULT_PROTECTED_WORKS
        # Keep a verbatim-name fast path even with embeddings (names are unambiguous).
        self.protected_terms = [t.lower() for t in (protected_terms or DEFAULT_PROTECTED_TERMS)]
        logger.info("loading embedding model %s", model)
        self._model = SentenceTransformer(model)
        self._work_emb = self._model.encode(self.protected_works, convert_to_tensor=True, normalize_embeddings=True)

    def detect(self, text: str) -> CopyrightResult:  # pragma: no cover - needs the model
        low = text.lower()
        named = [t for t in self.protected_terms if t in low]
        if named:
            return CopyrightResult(risk=0.95, matched=named[0], detail=f"protected IP named verbatim: {named}")
        q = self._model.encode([text], convert_to_tensor=True, normalize_embeddings=True)
        sims = self._util.cos_sim(q, self._work_emb)[0]
        best = float(sims.max())
        idx = int(sims.argmax())
        risk = max(0.0, min(1.0, best))
        if best >= self.threshold:
            return CopyrightResult(
                risk=risk, matched=self.protected_works[idx],
                detail=f"embedding similarity {best:.2f} to protected work",
            )
        return CopyrightResult(risk=risk * 0.3, detail=f"low embedding similarity ({best:.2f})")


BACKEND_REGISTRY: dict[str, type] = {
    "jaccard": JaccardBackend,
    "embedding": EmbeddingCopyrightBackend,
}


def build_copyright_backend(name: str, **params) -> CopyrightBackend:
    cls = BACKEND_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown copyright backend {name!r}; expected one of {sorted(BACKEND_REGISTRY)}")
    return cls(**params)
