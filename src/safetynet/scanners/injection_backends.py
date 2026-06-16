"""Pluggable detection backends for the prompt-injection scanner.

A backend returns an injection ``risk`` in [0, 1] (1.0 = clear injection attempt). The
:class:`PromptInjectionScanner` converts that to the project-wide *safety* score.

Backends:
  * :class:`PatternBackend` — dependency-free default: known injection phrasings. Always available.
  * :class:`PromptGuardBackend` — LlamaFirewall PromptGuard 2 (arXiv:2505.03574) via HuggingFace
    ``transformers`` text classification. Optional extra ``[guard]``; lazy import; fail-closed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .normalize import find_terms

logger = logging.getLogger("safetynet.scanners.injection_backends")

DEFAULT_INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all previous",
    "ignore the above",
    "disregard the above",
    "disregard previous",
    "disregard all prior",
    "forget previous instructions",
    "forget everything",
    "reveal your system prompt",
    "print your system prompt",
    "repeat the words above",
    "you are now",
    "act as",
    "pretend you are",
    "developer mode",
    "dan mode",
    "jailbreak",
    "do anything now",
    "without any restrictions",
    "ignore your guidelines",
    "override your guidelines",
    "bypass your safety",
    "new instructions:",
    "system prompt:",
]


@dataclass
class InjectionResult:
    risk: float
    matched: list[str] = field(default_factory=list)
    detail: str = ""


@runtime_checkable
class InjectionBackend(Protocol):
    name: str

    def detect(self, text: str) -> InjectionResult:
        ...


class PatternBackend:
    """Known-phrasing pattern matcher. The dependency-free default."""

    name = "pattern"

    def __init__(self, patterns: list[str] | None = None) -> None:
        self.patterns = [p.lower() for p in (patterns or DEFAULT_INJECTION_PATTERNS)]

    def detect(self, text: str) -> InjectionResult:
        # find_terms folds away homoglyphs, zero-width chars, leetspeak, spacing, and Base64.
        hits = find_terms(text, self.patterns)
        if hits:
            return InjectionResult(risk=0.95, matched=hits, detail=f"injection patterns: {hits}")
        return InjectionResult(risk=0.04, detail="no injection patterns detected")


DEFAULT_PROMPTGUARD_MODEL = "meta-llama/Llama-Prompt-Guard-2-86M"


class PromptGuardBackend:
    """LlamaFirewall PromptGuard 2 classifier via transformers.

    Optional: requires ``pip install '.[guard]'`` (transformers + torch) and the model weights.
    """

    name = "promptguard"

    def __init__(self, model_id: str = DEFAULT_PROMPTGUARD_MODEL, threshold: float = 0.5) -> None:
        try:
            from transformers import pipeline
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "PromptGuardBackend requires the optional 'guard' extra. "
                "Install with: pip install '.[guard]'"
            ) from exc

        self.model_id = model_id
        self.threshold = threshold
        logger.info("loading PromptGuard model %s", model_id)
        self._pipe = pipeline("text-classification", model=model_id)

    def detect(self, text: str) -> InjectionResult:  # pragma: no cover - needs the model
        preds = self._pipe(text, truncation=True)
        pred = preds[0] if isinstance(preds, list) else preds
        label = str(pred.get("label", "")).upper()
        score = float(pred.get("score", 0.0))
        # PromptGuard labels malicious classes (e.g. "INJECTION"/"JAILBREAK"/"LABEL_1").
        is_attack = label not in {"BENIGN", "SAFE", "LABEL_0"}
        risk = score if is_attack else (1.0 - score)
        return InjectionResult(
            risk=max(0.0, min(1.0, risk)), matched=[label],
            detail=f"promptguard label={label} score={score:.2f}",
        )


BACKEND_REGISTRY: dict[str, type] = {
    "pattern": PatternBackend,
    "promptguard": PromptGuardBackend,
}


def build_injection_backend(name: str, **params) -> InjectionBackend:
    cls = BACKEND_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown injection backend {name!r}; expected one of {sorted(BACKEND_REGISTRY)}")
    return cls(**params)
