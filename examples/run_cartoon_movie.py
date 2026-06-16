"""End-to-end demo: a benign run that passes, and an adversarial run that gets halted.

Run from the repo root:

    python examples/run_cartoon_movie.py

Outputs are written to ``output/audit-<run_id>.jsonl`` and operational logs to ``logs/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without `pip install -e .` by adding src/ to the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml  # noqa: E402

from safetynet.core.logging_config import configure_logging  # noqa: E402
from safetynet.core.policy import load_policy  # noqa: E402
from safetynet.pipeline import build_default_pipeline  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _print_report(label: str, report) -> None:
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(f"run_id    : {report.run_id}")
    print(f"halted    : {report.halted}")
    if report.halt_reason:
        print(f"halt_reason: {report.halt_reason}")
    print(f"audit log : {report.audit_path}")
    print("node decisions:")
    for r in report.node_results:
        print(f"  - {r.node_id:<13} {r.stage.value:<4} -> {r.aggregate.decision.value:<5} "
              f"(score {r.aggregate.score:.2f}) {r.aggregate.rationale[:60]}")


def main() -> None:
    configure_logging()
    policy = load_policy(ROOT / "policies" / "default.yaml")
    bible = yaml.safe_load((ROOT / "policies" / "character_bible.yaml").read_text(encoding="utf-8"))

    print(f"Loaded policy v{policy.version} (hash {policy.policy_hash[:12]}…), stance={policy.stance}")

    # 1) Benign brief — should pass all gates.
    benign = build_default_pipeline(policy, character_bible=bible)
    benign_report = benign.run(
        "Pip and Wren plant a hopeful garden in the Clockwork Meadow; gentle and heartwarming."
    )
    _print_report("BENIGN RUN", benign_report)

    # 2) Adversarial brief — names an INVENTED placeholder IP + harmful content.
    #    Expect copyright + content scanners to fire, deontology to veto, breaker to halt.
    adversarial = build_default_pipeline(policy, character_bible=bible)
    adversarial_report = adversarial.run(
        "Recreate Captain Sprocket from the Glimmertown franchise in a scene with gore and "
        "graphic violence where the hero lies to a child."
    )
    _print_report("ADVERSARIAL RUN", adversarial_report)

    print("\nDone. Inspect the JSONL audit logs above for the full per-node trace.")


if __name__ == "__main__":
    main()
