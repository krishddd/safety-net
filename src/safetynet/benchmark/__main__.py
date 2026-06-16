"""CLI: python -m safetynet.benchmark [--dataset PATH --format FMT] [--policy PATH] [--block-only]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..core.logging_config import configure_logging
from ..core.policy import load_policy
from .harness import run_benchmark
from .loaders import (
    load_agentsafetybench,
    load_copyright_sample,
    load_jsonl,
    load_rjudge,
    load_sample,
)

DEFAULT_POLICY = Path(__file__).resolve().parents[3] / "policies" / "default.yaml"


def _load(dataset: str | None, fmt: str, sample: str):
    if not dataset:
        return load_copyright_sample() if sample == "copyright" else load_sample()
    if fmt == "rjudge":
        return load_rjudge(dataset)
    if fmt == "agentsafetybench":
        return load_agentsafetybench(dataset)
    return load_jsonl(dataset)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="safetynet.benchmark", description="Benchmark SafetyNet detection.")
    parser.add_argument("--dataset", help="Path to a dataset file (defaults to the bundled sample).")
    parser.add_argument(
        "--format", choices=["jsonl", "rjudge", "agentsafetybench"], default="jsonl",
        help="Dataset format (ignored when --dataset is omitted).",
    )
    parser.add_argument(
        "--sample", choices=["agent", "copyright"], default="agent",
        help="Which bundled sample to use when --dataset is omitted.",
    )
    parser.add_argument("--policy", default=str(DEFAULT_POLICY), help="Policy YAML to evaluate under.")
    parser.add_argument(
        "--block-only", action="store_true",
        help="Count only BLOCK as a detection (default: FLAG also counts).",
    )
    args = parser.parse_args(argv)

    configure_logging(to_file=False)
    policy = load_policy(args.policy)
    scenarios = _load(args.dataset, args.format, args.sample)
    report = run_benchmark(scenarios, policy, flag_counts_as_unsafe=not args.block_only)

    print(f"Policy v{policy.version} (hash {policy.policy_hash[:12]}), stance={policy.stance}")
    print(report.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
