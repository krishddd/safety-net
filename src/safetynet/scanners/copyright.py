"""Copyright / IP scanner.

Delegates detection to a pluggable :class:`CopyrightBackend` (see ``copyright_backends.py``).
The default ``jaccard`` backend is dependency-free; selecting ``embedding`` wires in GoG-style
(arXiv:2503.16171) embedding similarity. This scanner is the single place a backend's infringement
``risk`` is converted to the project-wide *safety* score (``safety = 1 - risk``).
"""

from __future__ import annotations

from ..core.types import Action, Context, Verdict
from .copyright_backends import (
    DEFAULT_PROTECTED_TERMS,
    CopyrightBackend,
    build_copyright_backend,
)

__all__ = ["CopyrightScanner", "DEFAULT_PROTECTED_TERMS"]


class CopyrightScanner:
    name = "copyright"

    def __init__(
        self,
        backend: str | CopyrightBackend = "jaccard",
        protected_terms: list[str] | None = None,
        threshold: float = 0.18,
        model: str | None = None,
        **backend_params,
    ) -> None:
        if isinstance(backend, str):
            params = dict(backend_params)
            if protected_terms is not None:
                params["protected_terms"] = protected_terms
            if backend == "jaccard":
                params["threshold"] = threshold
            if model is not None and backend == "embedding":
                params["model"] = model
            self.backend: CopyrightBackend = build_copyright_backend(backend, **params)
        else:
            self.backend = backend

    def scan(self, action: Action, context: Context) -> Verdict:
        result = self.backend.detect(action.payload)
        safety = max(0.0, 1.0 - float(result.risk))
        return Verdict.from_score(self.name, safety, f"[{self.backend.name}] {result.detail}")
