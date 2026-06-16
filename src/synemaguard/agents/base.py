"""The agent interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..core.types import Action, Context


@runtime_checkable
class Agent(Protocol):
    """A generative node. ``kind`` is the Action kind it produces."""

    node_id: str
    kind: str

    def run(self, action: Action, context: Context) -> Any:
        ...
