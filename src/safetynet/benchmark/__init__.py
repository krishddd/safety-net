"""Benchmark harness for evaluating SafetyNet against agent-safety datasets.

Runs labeled scenarios (R-Judge, Agent-SafetyBench, or a generic JSONL schema) through a
SafetyNet gate and reports detection metrics (accuracy, precision, recall, F1, confusion).

The real datasets require download; a small offline sample ships in ``benchmark/data`` so the
harness — and its tests — run with no network. Point ``--dataset`` at a real file to use it.
"""

from .harness import build_evaluator, run_benchmark
from .loaders import load_agentsafetybench, load_jsonl, load_rjudge, load_sample
from .metrics import ConfusionMatrix, confusion
from .types import BenchmarkReport, Scenario, ScenarioResult

__all__ = [
    "Scenario",
    "ScenarioResult",
    "BenchmarkReport",
    "ConfusionMatrix",
    "confusion",
    "run_benchmark",
    "build_evaluator",
    "load_jsonl",
    "load_rjudge",
    "load_agentsafetybench",
    "load_sample",
]
