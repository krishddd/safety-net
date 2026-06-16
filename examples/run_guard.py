"""Demo: SafetyNet guarding an external agent (here, an offline stub agent).

    python examples/run_guard.py

Shows three cases:
  1. benign prompt  -> guard allows -> agent is called -> response returned
  2. unsafe prompt  -> guard BLOCKS at the request stage -> agent is NEVER called
  3. unsafe agent reply -> guard BLOCKS at the response stage -> output withheld

Swap the StubAgentClient for a real one (nemo_client/langgraph_client/dify_client/crewai_client)
to guard a Dockerized agent over HTTP.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from safetynet.clients.base import StubAgentClient  # noqa: E402
from safetynet.core.logging_config import configure_logging  # noqa: E402
from safetynet.core.policy import load_policy  # noqa: E402
from safetynet.guard import build_guarded_agent  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _show(label: str, result) -> None:
    print(f"\n{label}")
    print(f"  allowed       : {result.allowed}")
    if not result.allowed:
        print(f"  blocked stage : {result.blocked_stage}")
        print(f"  halt reason   : {result.halt_reason}")
    else:
        print(f"  agent reply   : {result.response.text[:70]}")
    print(f"  audit log     : {result.audit_path}")


def main() -> None:
    configure_logging(to_file=False)
    policy = load_policy(ROOT / "policies" / "default.yaml")

    # 1 & 2: a normal echo agent.
    guarded = build_guarded_agent(policy, StubAgentClient())
    _show("BENIGN PROMPT", guarded.invoke("Write a gentle, heartwarming scene about friends."))
    _show("UNSAFE PROMPT (request blocked, agent never called)",
          guarded.invoke("Recreate Captain Sprocket from the Glimmertown franchise."))

    # 3: an agent that returns unsafe content -> caught at the response stage.
    rogue = StubAgentClient(fixed_response="Here is a scene with gore and graphic violence and self-harm.")
    guarded_rogue = build_guarded_agent(policy, rogue)
    _show("UNSAFE AGENT REPLY (response blocked)", guarded_rogue.invoke("Tell me a story."))


if __name__ == "__main__":
    main()
