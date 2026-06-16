"""Character-bible structural validator (stub).

Swap-in point for Guardrails AI RAIL schemas / NeMo Colang rules. The stub enforces that a
script action references at least one canonical character and violates no banned traits from
the project's character bible (provided via ``context.character_bible``).
"""

from __future__ import annotations

from ..core.types import Action, Context, Verdict
from .base import tokenize


class CharacterBibleScanner:
    name = "character_bible"

    def __init__(self, applies_to_kinds: tuple[str, ...] = ("generate_script",)) -> None:
        self.applies_to_kinds = applies_to_kinds

    def scan(self, action: Action, context: Context) -> Verdict:
        bible = context.character_bible or {}
        canonical = [c.lower() for c in bible.get("characters", [])]
        banned_traits = [t.lower() for t in bible.get("banned_traits", [])]

        # Only structurally constrain the kinds we own (e.g. script generation).
        if action.kind not in self.applies_to_kinds or not canonical:
            return Verdict.from_score(self.name, 0.9, "no character-bible constraints apply")

        text = action.payload.lower()
        tokens = set(tokenize(action.payload))

        trait_hits = [t for t in banned_traits if t in text]
        if trait_hits:
            return Verdict.from_score(
                self.name, 0.2, f"banned character traits present: {trait_hits}"
            )

        mentions_canonical = any(c in text or c in tokens for c in canonical)
        if not mentions_canonical:
            return Verdict.from_score(
                self.name, 0.5, "no canonical character referenced (structure check)"
            )
        return Verdict.from_score(self.name, 0.92, "references canonical character; no banned traits")
