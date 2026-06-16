"""Pluggable content/security scanners.

Every scanner emits a :class:`Verdict` using the **same safety-direction convention as the
ethics engine** (``score``: 1.0 = safe, 0.0 = unsafe) and the same ``band()`` helper, so a
scanner author thinking in "risk" or "similarity" terms cannot silently flip the sign.

Phase-1 scanners are deterministic, dependency-light stubs (stdlib only). Each is a swap-in
point for a real model documented in docs/CONCEPTS.md (LlamaGuard, GoG/CopyJudge, LlamaFirewall).
"""

from .base import Scanner
from .character_bible import CharacterBibleScanner
from .content_safety import ContentSafetyScanner
from .copyright import CopyrightScanner
from .moderation import (
    AnthropicModerationBackend,
    KeywordBackend,
    ModerationBackend,
    ModerationResult,
    TransformersGuardBackend,
    build_backend,
)
from .prompt_injection import PromptInjectionScanner

__all__ = [
    "Scanner",
    "ContentSafetyScanner",
    "CopyrightScanner",
    "PromptInjectionScanner",
    "CharacterBibleScanner",
    # moderation backends
    "ModerationBackend",
    "ModerationResult",
    "KeywordBackend",
    "TransformersGuardBackend",
    "AnthropicModerationBackend",
    "build_backend",
]
