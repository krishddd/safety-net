"""Dataset loaders.

A generic JSONL loader plus tolerant adapters for R-Judge and Agent-SafetyBench, whose exact
schemas vary by release — the adapters look for the most common keys and fall back gracefully.
Point them at the real downloaded files; a bundled sample lets everything run offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from .types import Scenario

SAMPLE_PATH = Path(__file__).parent / "data" / "sample_scenarios.jsonl"
COPYRIGHT_SAMPLE_PATH = Path(__file__).parent / "data" / "copyright_sample.jsonl"


def _read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    records = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _truthy_unsafe(value) -> bool:
    """Interpret a label as 'unsafe'. Handles 1/0, true/false, 'unsafe'/'safe', 'risk'."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    return s in {"1", "true", "unsafe", "risk", "risky", "harmful", "yes", "unsafe."}


def load_jsonl(
    path: str | Path,
    text_key: str = "text",
    label_key: str = "expected_unsafe",
    source: str = "custom",
) -> list[Scenario]:
    """Load a generic JSONL file into Scenarios."""
    out = []
    for i, rec in enumerate(_read_jsonl(path)):
        out.append(
            Scenario(
                id=str(rec.get("id", i)),
                text=str(rec[text_key]),
                expected_unsafe=_truthy_unsafe(rec.get(label_key)),
                source=rec.get("source", source),
                category=str(rec.get("category", "")),
                meta={k: v for k, v in rec.items() if k not in {"id", text_key, label_key, "source", "category"}},
            )
        )
    return out


def _first_present(rec: dict, keys: list[str], default=None):
    for k in keys:
        if k in rec and rec[k] not in (None, ""):
            return rec[k]
    return default


def load_rjudge(path: str | Path) -> list[Scenario]:
    """Tolerant R-Judge loader (interaction records labeled with a risk flag)."""
    out = []
    for i, rec in enumerate(_read_jsonl(path)):
        text = _first_present(rec, ["contents", "conversation", "scenario", "text", "profile"], "")
        if isinstance(text, list):
            text = " ".join(
                m.get("content", str(m)) if isinstance(m, dict) else str(m) for m in text
            )
        label = _first_present(rec, ["label", "risk", "is_safe", "safe"], 1)
        # Some schemas use is_safe/safe (invert): if the key implies safety, flip it.
        unsafe = _truthy_unsafe(label)
        if any(k in rec for k in ("is_safe", "safe")) and "label" not in rec and "risk" not in rec:
            unsafe = not _truthy_unsafe(label)
        out.append(
            Scenario(
                id=str(rec.get("id", i)),
                text=str(text),
                expected_unsafe=unsafe,
                source="r-judge",
                category=str(_first_present(rec, ["risk_type", "category", "scenario"], "")),
            )
        )
    return out


def load_agentsafetybench(path: str | Path) -> list[Scenario]:
    """Tolerant Agent-SafetyBench loader (task/instruction records labeled safe/unsafe)."""
    out = []
    for i, rec in enumerate(_read_jsonl(path)):
        text = _first_present(rec, ["instruction", "prompt", "query", "task", "text"], "")
        label = _first_present(rec, ["label", "unsafe", "is_unsafe", "safe", "is_safe"], None)
        unsafe = _truthy_unsafe(label)
        if any(k in rec for k in ("safe", "is_safe")) and not any(k in rec for k in ("label", "unsafe", "is_unsafe")):
            unsafe = not _truthy_unsafe(label)
        out.append(
            Scenario(
                id=str(rec.get("id", i)),
                text=str(text),
                expected_unsafe=unsafe,
                source="agent-safetybench",
                category=str(_first_present(rec, ["category", "risk_category", "type"], "")),
            )
        )
    return out


def load_sample() -> list[Scenario]:
    """Load the bundled offline general sample dataset."""
    return load_jsonl(SAMPLE_PATH, source="sample")


def load_copyright_sample() -> list[Scenario]:
    """Load the bundled offline copyright-reproduction sample.

    A text-prompt analogue of the copyright-reproduction benchmark (arXiv:2403.12052): IP-naming
    prompts (should be caught) vs. original-content prompts (should pass). The real image-level
    benchmark scores CLIP similarity of *generated images* to protected works — wire that in via
    the ImageModerationScanner + an embedding/CLIP vision backend for the visual extension.
    """
    return load_jsonl(COPYRIGHT_SAMPLE_PATH, source="copyright-sample")
