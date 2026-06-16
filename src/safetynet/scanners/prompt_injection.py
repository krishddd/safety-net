"""Prompt-injection scanner (stub).

Swap-in point for LlamaFirewall PromptGuard 2 (arXiv:2505.03574). The stub matches well-known
injection phrasings; a hit sharply lowers the safety score.
"""

from __future__ import annotations

from ..core.types import Action, Context, Verdict

DEFAULT_INJECTION_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard the above",
    "disregard previous",
    "reveal your system prompt",
    "you are now",
    "developer mode",
    "jailbreak",
    "do anything now",
    "override your guidelines",
]


class PromptInjectionScanner:
    name = "prompt_injection"

    def __init__(self, patterns: list[str] | None = None) -> None:
        self.patterns = [p.lower() for p in (patterns or DEFAULT_INJECTION_PATTERNS)]

    def scan(self, action: Action, context: Context) -> Verdict:
        text = action.payload.lower()
        hits = [p for p in self.patterns if p in text]
        if hits:
            return Verdict.from_score(
                self.name, 0.05, f"prompt-injection patterns detected: {hits}"
            )
        return Verdict.from_score(self.name, 0.96, "no prompt-injection patterns detected")
