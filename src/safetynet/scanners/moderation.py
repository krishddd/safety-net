"""Pluggable moderation backends for the content-safety scanner.

This is the seam where a *real* guard model is wired in. A backend takes text and returns a
:class:`ModerationResult` with an ``unsafe_score`` in [0, 1] (1.0 = maximally unsafe) plus the
categories it tripped. The :class:`~safetynet.scanners.content_safety.ContentSafetyScanner`
converts that to the project-wide *safety* score (``safety = 1 - unsafe_score``) in exactly one
place, so the sign convention is never ambiguous.

Backends:
  * :class:`KeywordBackend` — dependency-free default (the Phase-1 stub logic). Always available.
  * :class:`TransformersGuardBackend` — local open guard model (LlamaGuard / ShieldGemma) via
    HuggingFace ``transformers``. Optional extra ``[guard]``; lazy import; fail-closed.
  * :class:`AnthropicModerationBackend` — LLM-as-judge using the Anthropic SDK. Optional extra
    ``[anthropic]``; lazy import; needs ``ANTHROPIC_API_KEY``; fail-closed.

All heavy backends import their dependency lazily inside ``__init__`` so importing this module
never requires them, and a missing dependency raises a clear, actionable error.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .normalize import find_terms

logger = logging.getLogger("safetynet.scanners.moderation")


@dataclass
class ModerationResult:
    """Outcome of a moderation backend. ``unsafe_score``: 0.0 = safe, 1.0 = maximally unsafe."""

    unsafe_score: float
    categories: list[str] = field(default_factory=list)
    detail: str = ""


@runtime_checkable
class ModerationBackend(Protocol):
    name: str

    def classify(self, text: str) -> ModerationResult:
        ...


# --- Default: keyword backend (no dependencies) -------------------------------------------

DEFAULT_UNSAFE_TERMS: dict[str, float] = {
    "gore": 0.5,
    "graphic violence": 0.6,
    "decapitation": 0.7,
    "torture": 0.6,
    "explicit": 0.5,
    "self-harm": 0.8,
    "weapon how-to": 0.7,
}


class KeywordBackend:
    """Deterministic keyword backend — the dependency-free default."""

    name = "keyword"

    def __init__(self, unsafe_terms: dict[str, float] | None = None) -> None:
        self.unsafe_terms = {k.lower(): float(v) for k, v in (unsafe_terms or DEFAULT_UNSAFE_TERMS).items()}

    def classify(self, text: str) -> ModerationResult:
        # find_terms folds away obfuscation (homoglyphs, zero-width, leetspeak, spacing, Base64).
        matched = find_terms(text, list(self.unsafe_terms))
        hits = {term: self.unsafe_terms[term] for term in matched}
        if not hits:
            return ModerationResult(unsafe_score=0.05, categories=[], detail="no unsafe content terms detected")
        worst = max(hits.values())
        unsafe = min(1.0, worst + 0.05 * (len(hits) - 1))
        return ModerationResult(
            unsafe_score=unsafe,
            categories=sorted(hits),
            detail=f"unsafe content terms: {sorted(hits)}",
        )


# --- Real model: local open guard model via transformers ----------------------------------

# Common open guard models. Llama Guard / ShieldGemma emit "safe"/"unsafe" tokens; this backend
# reads the unsafe probability from the first generated token's logits.
DEFAULT_GUARD_MODEL = "meta-llama/Llama-Guard-3-8B"


class TransformersGuardBackend:
    """Local open guard model (LlamaGuard / ShieldGemma) via HuggingFace transformers.

    Optional: requires ``pip install '.[guard]'`` (transformers + torch) and a downloaded,
    possibly gated, model. Construction loads the model eagerly so failures surface early; the
    scanner wraps :meth:`classify` in a fail-closed try/except.
    """

    name = "transformers"

    def __init__(self, model_id: str = DEFAULT_GUARD_MODEL, device: str | None = None) -> None:
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "TransformersGuardBackend requires the optional 'guard' extra. "
                "Install with: pip install '.[guard]'"
            ) from exc

        self.model_id = model_id
        self._torch = __import__("torch")
        logger.info("loading guard model %s (this may download weights)", model_id)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id)
        if device:
            self.model = self.model.to(device)
        self.model.eval()

    def classify(self, text: str) -> ModerationResult:  # pragma: no cover - needs heavy model
        torch = self._torch
        # Guard models expect a chat-formatted moderation prompt.
        messages = [{"role": "user", "content": text}]
        input_ids = self.tokenizer.apply_chat_template(messages, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(input_ids, max_new_tokens=8, output_scores=True, return_dict_in_generate=True)
        decoded = self.tokenizer.decode(out.sequences[0][input_ids.shape[-1]:], skip_special_tokens=True).strip().lower()
        unsafe = 1.0 if decoded.startswith("unsafe") else 0.05
        # Categories typically follow on the next line(s).
        categories = [c.strip() for c in decoded.splitlines()[1:] if c.strip()]
        return ModerationResult(unsafe_score=unsafe, categories=categories, detail=f"guard model verdict: {decoded!r}")


# --- Real model: LLM-as-judge via the Anthropic SDK ---------------------------------------

ANTHROPIC_MODERATION_MODEL = "claude-haiku-4-5-20251001"  # fast + cheap classifier tier

_MODERATION_SYSTEM = (
    "You are a strict content-safety classifier for a children's animated-movie pipeline. "
    "Given a piece of text (a script line or an image/video prompt), assess how unsafe it is. "
    "Respond ONLY with a compact JSON object: "
    '{"unsafe_score": <float 0..1>, "categories": [<short strings>], "reason": "<one sentence>"}. '
    "1.0 means clearly unsafe (graphic violence, sexual content, self-harm, hate, real-world "
    "harm instructions); 0.0 means clearly safe and age-appropriate."
)


class AnthropicModerationBackend:
    """LLM-as-judge moderation using the Anthropic SDK (Claude).

    Optional: requires ``pip install '.[anthropic]'`` and the ``ANTHROPIC_API_KEY`` env var.
    Uses a fast/cheap model tier by default. Network and key errors propagate to the scanner's
    fail-closed handler.
    """

    name = "anthropic"

    def __init__(self, model: str = ANTHROPIC_MODERATION_MODEL, max_tokens: int = 256, api_key: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "AnthropicModerationBackend requires the optional 'anthropic' extra. "
                "Install with: pip install '.[anthropic]'"
            ) from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("AnthropicModerationBackend needs ANTHROPIC_API_KEY (or api_key=...)")
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=key)

    def classify(self, text: str) -> ModerationResult:  # pragma: no cover - needs network + key
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=_MODERATION_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        raw = "".join(block.text for block in msg.content if getattr(block, "type", None) == "text").strip()
        data = _extract_json(raw)
        score = float(data.get("unsafe_score", 1.0))  # default to unsafe if the field is missing
        return ModerationResult(
            unsafe_score=max(0.0, min(1.0, score)),
            categories=list(data.get("categories", [])),
            detail=str(data.get("reason", raw))[:200],
        )


def _extract_json(raw: str) -> dict:
    """Best-effort parse of a JSON object from a model response."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError(f"could not parse moderation JSON from: {raw!r}")


# --- Registry: policy selects a backend by name -------------------------------------------

BACKEND_REGISTRY: dict[str, type] = {
    "keyword": KeywordBackend,
    "transformers": TransformersGuardBackend,
    "anthropic": AnthropicModerationBackend,
}


def build_backend(name: str, **params) -> ModerationBackend:
    """Instantiate a moderation backend by registry name."""
    cls = BACKEND_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown moderation backend {name!r}; expected one of {sorted(BACKEND_REGISTRY)}")
    return cls(**params)
