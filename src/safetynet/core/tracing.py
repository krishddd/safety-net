"""Pluggable run tracing (observability), complementary to the JSONL audit log.

The audit log is the tamper-evident record; a :class:`Tracer` is for live observability dashboards.
Default is :class:`NullTracer` (no-op). :class:`LangfuseTracer` (optional ``[langfuse]`` extra)
emits a trace per run and a span per node/stage decision. :class:`RecordingTracer` keeps events
in memory for tests.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from .types import NodeResult

logger = logging.getLogger("safetynet.tracing")


@runtime_checkable
class Tracer(Protocol):
    def start_run(self, run_id: str, metadata: dict[str, Any]) -> None:
        ...

    def record(self, result: NodeResult, breaker_state: dict[str, Any]) -> None:
        ...

    def end_run(self, summary: dict[str, Any]) -> None:
        ...


class NullTracer:
    """No-op tracer; the default."""

    def start_run(self, run_id: str, metadata: dict[str, Any]) -> None:
        pass

    def record(self, result: NodeResult, breaker_state: dict[str, Any]) -> None:
        pass

    def end_run(self, summary: dict[str, Any]) -> None:
        pass


class RecordingTracer:
    """Captures trace events in memory (handy for tests / debugging)."""

    def __init__(self) -> None:
        self.runs: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.summaries: list[dict[str, Any]] = []

    def start_run(self, run_id: str, metadata: dict[str, Any]) -> None:
        self.runs.append({"run_id": run_id, **metadata})

    def record(self, result: NodeResult, breaker_state: dict[str, Any]) -> None:
        self.events.append(
            {
                "node_id": result.node_id,
                "stage": result.stage.value,
                "decision": result.aggregate.decision.value,
                "score": round(result.aggregate.score, 4),
                "breaker": breaker_state,
            }
        )

    def end_run(self, summary: dict[str, Any]) -> None:
        self.summaries.append(summary)


class LangfuseTracer:
    """Emit traces/spans to Langfuse. Optional ``[langfuse]`` extra; lazy import.

    Errors from the tracing client are swallowed (observability must never break the pipeline).
    """

    def __init__(self, public_key: str | None = None, secret_key: str | None = None, host: str | None = None) -> None:
        try:
            from langfuse import Langfuse
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "LangfuseTracer requires the optional 'langfuse' extra. Install: pip install '.[langfuse]'"
            ) from exc
        kwargs = {k: v for k, v in {"public_key": public_key, "secret_key": secret_key, "host": host}.items() if v}
        self._client = Langfuse(**kwargs)
        self._trace = None

    def start_run(self, run_id: str, metadata: dict[str, Any]) -> None:  # pragma: no cover - needs service
        try:
            self._trace = self._client.trace(name="safetynet-run", id=run_id, metadata=metadata)
        except Exception:  # noqa: BLE001
            logger.exception("langfuse start_run failed; continuing without tracing")
            self._trace = None

    def record(self, result: NodeResult, breaker_state: dict[str, Any]) -> None:  # pragma: no cover - needs service
        if self._trace is None:
            return
        try:
            self._trace.span(
                name=f"{result.node_id}:{result.stage.value}",
                metadata={
                    "decision": result.aggregate.decision.value,
                    "score": result.aggregate.score,
                    "rationale": result.aggregate.rationale,
                    "breaker": breaker_state,
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("langfuse record failed; continuing")

    def end_run(self, summary: dict[str, Any]) -> None:  # pragma: no cover - needs service
        try:
            if self._trace is not None:
                self._trace.update(metadata={"summary": summary})
            self._client.flush()
        except Exception:  # noqa: BLE001
            logger.exception("langfuse end_run failed; continuing")
