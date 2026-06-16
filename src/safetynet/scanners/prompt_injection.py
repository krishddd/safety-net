"""Prompt-injection scanner.

Delegates to a pluggable :class:`InjectionBackend` (see ``injection_backends.py``). The default
``pattern`` backend is dependency-free; selecting ``promptguard`` wires in LlamaFirewall
PromptGuard 2 (arXiv:2505.03574). This scanner converts a backend's injection ``risk`` to the
project-wide *safety* score (``safety = 1 - risk``).
"""

from __future__ import annotations

from ..core.types import Action, Context, Verdict
from .injection_backends import (
    DEFAULT_INJECTION_PATTERNS,
    InjectionBackend,
    build_injection_backend,
)

__all__ = ["PromptInjectionScanner", "DEFAULT_INJECTION_PATTERNS"]


class PromptInjectionScanner:
    name = "prompt_injection"

    def __init__(
        self,
        backend: str | InjectionBackend = "pattern",
        patterns: list[str] | None = None,
        model_id: str | None = None,
        **backend_params,
    ) -> None:
        if isinstance(backend, str):
            params = dict(backend_params)
            if backend == "pattern" and patterns is not None:
                params["patterns"] = patterns
            if model_id is not None and backend == "promptguard":
                params["model_id"] = model_id
            self.backend: InjectionBackend = build_injection_backend(backend, **params)
        else:
            self.backend = backend

    def scan(self, action: Action, context: Context) -> Verdict:
        result = self.backend.detect(action.payload)
        safety = max(0.0, 1.0 - float(result.risk))
        return Verdict.from_score(self.name, safety, f"[{self.backend.name}] {result.detail}")
