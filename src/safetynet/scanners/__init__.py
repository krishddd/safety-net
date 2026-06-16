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
from .copyright_backends import (
    CopyrightBackend,
    EmbeddingCopyrightBackend,
    JaccardBackend,
    build_copyright_backend,
)
from .image_moderation import (
    AzureVisionBackend,
    ImageModerationScanner,
    NullVisionBackend,
    RekognitionBackend,
    TransformersNSFWBackend,
    VisionBackend,
    build_vision_backend,
)
from .injection_backends import (
    InjectionBackend,
    PatternBackend,
    PromptGuardBackend,
    build_injection_backend,
)
from .moderation import (
    AnthropicModerationBackend,
    KeywordBackend,
    ModerationBackend,
    ModerationResult,
    TransformersGuardBackend,
    build_backend,
)
from .pii import PIIScanner
from .prompt_injection import PromptInjectionScanner

__all__ = [
    "Scanner",
    "ContentSafetyScanner",
    "CopyrightScanner",
    "PromptInjectionScanner",
    "CharacterBibleScanner",
    "ImageModerationScanner",
    "PIIScanner",
    # content-safety moderation backends
    "ModerationBackend",
    "ModerationResult",
    "KeywordBackend",
    "TransformersGuardBackend",
    "AnthropicModerationBackend",
    "build_backend",
    # copyright backends
    "CopyrightBackend",
    "JaccardBackend",
    "EmbeddingCopyrightBackend",
    "build_copyright_backend",
    # injection backends
    "InjectionBackend",
    "PatternBackend",
    "PromptGuardBackend",
    "build_injection_backend",
    # vision backends
    "VisionBackend",
    "NullVisionBackend",
    "AzureVisionBackend",
    "RekognitionBackend",
    "TransformersNSFWBackend",
    "build_vision_backend",
]
