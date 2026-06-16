"""Run the SafetyNet benchmark harness on the bundled offline sample.

    python examples/run_benchmark.py

Point it at a real dataset instead with the CLI:

    python -m safetynet.benchmark --dataset path/to/r-judge.jsonl --format rjudge
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from safetynet.benchmark import load_sample, run_benchmark  # noqa: E402
from safetynet.core.logging_config import configure_logging  # noqa: E402
from safetynet.core.policy import load_policy  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    configure_logging(to_file=False)
    policy = load_policy(ROOT / "policies" / "default.yaml")
    scenarios = load_sample()

    print(f"Evaluating {len(scenarios)} sample scenarios under policy v{policy.version} "
          f"(stance={policy.stance})\n")

    # "Did the guard notice" (FLAG or BLOCK counts).
    report = run_benchmark(scenarios, policy, flag_counts_as_unsafe=True)
    print("=== Detection (FLAG or BLOCK counts as unsafe) ===")
    print(report.summary())

    # "Did the guard refuse" (only BLOCK counts).
    strict = run_benchmark(scenarios, policy, flag_counts_as_unsafe=False)
    print("\n=== Refusal (only BLOCK counts as unsafe) ===")
    print(strict.summary())


if __name__ == "__main__":
    main()
