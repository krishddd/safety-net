"""Evasion-resistant text normalization for the keyword/pattern scanners.

Character-injection attacks defeat naive substring guardrails at very high rates — emoji
smuggling and Unicode-tag smuggling reach ~80-100% evasion, plus homoglyphs, zero-width
characters, diacritics, full-width text, leetspeak, intra-letter spacing, and Base64 wrapping
(arXiv:2504.11168; Mindgard 2025). This module folds those obfuscations away **before** matching,
using only the stdlib (``unicodedata``, ``base64``, ``re``).

The original text is never mutated for output/audit (we hash the raw input); normalization only
produces the strings we *match against*.
"""

from __future__ import annotations

import base64
import re
import string
import unicodedata

_ASCII_TEXT = set(string.ascii_letters + string.digits + string.punctuation + " \t\n")

__all__ = ["strip_invisible", "fold", "normalize", "leet_fold", "despace", "decode_base64", "find_terms"]

# Zero-width, bidi-control, and joiner code points used to break up words invisibly.
_INVISIBLE_CODEPOINTS = {
    0x00AD,  # soft hyphen
    0x200B, 0x200C, 0x200D, 0x200E, 0x200F,  # ZWSP, ZWNJ, ZWJ, LRM, RLM
    0x2060, 0x2061, 0x2062, 0x2063, 0x2064,  # word joiner + invisible math ops
    0xFEFF,  # BOM / zero-width no-break space
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # bidi embeddings / overrides
    0x2066, 0x2067, 0x2068, 0x2069,  # bidi isolates
}


def _is_strippable(ch: str) -> bool:
    cp = ord(ch)
    if cp in _INVISIBLE_CODEPOINTS:
        return True
    if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:  # variation selectors (emoji smuggling)
        return True
    if 0xE0000 <= cp <= 0xE007F:  # Unicode tag block (tag smuggling)
        return True
    if ch in "\n\t":
        return False
    return unicodedata.category(ch) in ("Cf", "Cc")  # other format / control chars


def strip_invisible(text: str) -> str:
    """Remove zero-width, bidi, variation-selector, and tag-smuggling characters."""
    return "".join(c for c in text if not _is_strippable(c))


# Cross-script homoglyphs that NFKC does NOT fold (Cyrillic / Greek lookalikes).
# Built from explicit code points so the mapping can't depend on ambiguous source glyphs.
_CONFUSABLE_CODEPOINTS = {
    # Cyrillic lowercase -> Latin
    0x0430: "a", 0x0435: "e", 0x043A: "k", 0x043C: "m", 0x043D: "h", 0x043E: "o",
    0x0440: "p", 0x0441: "c", 0x0442: "t", 0x0443: "y", 0x0445: "x", 0x0455: "s",
    0x0456: "i", 0x0458: "j", 0x0501: "d", 0x0261: "g", 0x03BD: "v",
    # Cyrillic/Greek uppercase -> Latin
    0x0391: "A", 0x0392: "B", 0x0395: "E", 0x0396: "Z", 0x0397: "H", 0x0399: "I",
    0x039A: "K", 0x039C: "M", 0x039D: "N", 0x039F: "O", 0x03A1: "P", 0x03A4: "T",
    0x03A5: "Y", 0x03A7: "X",
    # Greek lowercase -> Latin
    0x03BF: "o", 0x03B1: "a", 0x03B5: "e", 0x03C1: "p",
}
_CONFUSABLES = {chr(cp): latin for cp, latin in _CONFUSABLE_CODEPOINTS.items()}


def fold(text: str) -> str:
    """Strip invisibles, NFKC (full-width/compat), map homoglyphs, drop diacritics."""
    text = strip_invisible(text)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(_CONFUSABLES.get(c, c) for c in text)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """Canonical lower-case form with collapsed whitespace, after :func:`fold`."""
    return re.sub(r"\s+", " ", fold(text).casefold()).strip()


_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "l"})


def leet_fold(text: str) -> str:
    return text.translate(_LEET)


def despace(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _looks_spaced_out(norm: str) -> bool:
    """True when text is mostly single-character tokens (the intra-letter-spacing attack).

    Gates the whitespace-removed match so normal prose ("go red" -> "gored") can't false-match
    a short term like "gore".
    """
    toks = norm.split()
    if len(toks) < 4:
        return False
    singles = sum(1 for t in toks if len(t) == 1)
    return singles >= max(4, len(toks) * 0.5)


_B64_RE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


def decode_base64(text: str, max_blobs: int = 8) -> list[str]:
    """Decode plausible Base64 blobs to surface payloads hidden behind encoding."""
    out: list[str] = []
    for m in _B64_RE.finditer(text):
        if len(out) >= max_blobs:
            break
        s = m.group(0)
        try:
            decoded = base64.b64decode(s + "=" * (-len(s) % 4), validate=False)
            t = decoded.decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            continue
        # Keep only blobs that decode to mostly-ASCII text (real payloads), not binary garbage
        # that a long ordinary word happens to base64-decode into.
        if t and sum(ch in _ASCII_TEXT for ch in t) >= 0.9 * len(t) and any(ch.isalpha() for ch in t):
            out.append(t)
    return out


def find_terms(text: str, terms: list[str]) -> list[str]:
    """Return which ``terms`` appear in ``text`` once obfuscation is folded away.

    Matches against the normalized form, a leetspeak fold, a whitespace-removed form (defeats
    intra-letter spacing), and any Base64-decoded payloads.
    """
    n = normalize(text)
    n_leet = leet_fold(n)
    n_despace = despace(n) if _looks_spaced_out(n) else None
    decoded = [normalize(d) for d in decode_base64(text)]
    found = []
    for term in terms:
        lt = term.lower()
        lt_despace = despace(lt)
        if (
            lt in n
            or lt in n_leet
            or (n_despace is not None and lt_despace and lt_despace in n_despace)
            or any(lt in d for d in decoded)
        ):
            found.append(term)
    return found
