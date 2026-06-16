"""Content-safety scanner.

Delegates the actual classification to a pluggable :class:`ModerationBackend` (see
``moderation.py``). The default ``keyword`` backend is dependency-free and reproduces the
Phase-1 stub behavior; selecting ``transformers`` (LlamaGuard/ShieldGemma) or ``anthropic``
(LLM-as-judge) wires in a real guard model with no other code changes.

This scanner is the single place where a backend's ``unsafe_score`` is converted to the
project-wide *safety* score (``safety = 1 - unsafe_score``).
"""

from __future__ import annotations

import logging

from ..core.types import Action, Context, Verdict
from .moderation import DEFAULT_UNSAFE_TERMS, ModerationBackend, build_backend

logger = logging.getLogger("safetynet.scanners.content_safety")

__all__ = ["ContentSafetyScanner", "DEFAULT_UNSAFE_TERMS"]


class ContentSafetyScanner:
    name = "content_safety"

    def __init__(
        self,
        backend: str | ModerationBackend = "keyword",
        unsafe_terms: dict[str, float] | None = None,
        model_id: str | None = None,
        **backend_params,
    ) -> None:
        """Create a content-safety scanner.

        Args:
            backend: a backend name (``keyword`` | ``transformers`` | ``anthropic``) or a ready
                :class:`ModerationBackend` instance (useful for tests / dependency injection).
            unsafe_terms: keyword lexicon for the ``keyword`` backend.
            model_id: model identifier for the ``transformers``/``anthropic`` backends.
            **backend_params: forwarded to the backend constructor.
        """
        if isinstance(backend, str):
            params = dict(backend_params)
            if backend == "keyword" and unsafe_terms is not None:
                params["unsafe_terms"] = unsafe_terms
            if model_id is not None and backend in ("transformers", "anthropic"):
                params["model" if backend == "anthropic" else "model_id"] = model_id
            self.backend: ModerationBackend = build_backend(backend, **params)
        else:
            self.backend = backend

    def scan(self, action: Action, context: Context) -> Verdict:
        result = self.backend.classify(action.payload)
        safety = max(0.0, 1.0 - float(result.unsafe_score))
        detail = result.detail or (
            f"unsafe categories: {result.categories}" if result.categories else "no unsafe content detected"
        )
        return Verdict.from_score(self.name, safety, f"[{self.backend.name}] {detail}")
