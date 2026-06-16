"""Tamper-evident audit log (JSONL).

One JSON object per node decision, written to ``output/audit-<run_id>.jsonl``. Content is
referenced by sha256 hash (not raw prompts/images) to keep the log shareable and PII-light.
The schema is fixed to satisfy EU AI Act Art. 13/14 and NIST AI RMF logging requirements:
each record is reconstructable against the exact ``policy_hash`` in effect.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import NodeResult

logger = logging.getLogger("synemaguard.audit")

DEFAULT_OUTPUT_DIR = Path("output")


def sha256_text(value: Any) -> str | None:
    """Hash arbitrary content to a hex digest; ``None`` passes through as ``None``."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLogger:
    """Appends structured decision records to a per-run JSONL file."""

    def __init__(self, run_id: str, policy_version: str, policy_hash: str, output_dir: Path | str = DEFAULT_OUTPUT_DIR) -> None:
        self.run_id = run_id
        self.policy_version = policy_version
        self.policy_hash = policy_hash
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / f"audit-{run_id}.jsonl"

    def record(
        self,
        result: NodeResult,
        *,
        input_payload: str | None,
        output_payload: Any | None,
        breaker_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Build, persist, and return one audit record."""
        record = {
            "ts": _now_iso(),
            "run_id": self.run_id,
            "node_id": result.node_id,
            "stage": result.stage.value,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "input_hash": sha256_text(input_payload),
            "output_hash": sha256_text(output_payload),
            "framework_verdicts": [v.to_dict() for v in result.framework_verdicts],
            "scanner_verdicts": [v.to_dict() for v in result.scanner_verdicts],
            "aggregate_decision": result.aggregate.decision.value,
            "aggregate_score": round(result.aggregate.score, 4),
            "aggregate_rationale": result.aggregate.rationale,
            "breaker_state": breaker_state,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        logger.debug("audit record written for %s/%s -> %s", result.node_id, result.stage.value, result.aggregate.decision.value)
        return record
