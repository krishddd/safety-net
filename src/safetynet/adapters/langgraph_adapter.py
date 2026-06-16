"""LangGraph adapter (optional).

Wraps a :class:`~safetynet.pipeline.Pipeline` as a LangGraph ``StateGraph`` so SafetyNet's
gates become graph nodes with conditional edges that route to ``END`` the moment the circuit
breaker halts. The import of ``langgraph`` is guarded: if it is not installed, ``AVAILABLE`` is
``False`` and :func:`build_state_graph` raises an informative error rather than crashing import.
"""

from __future__ import annotations

import logging

from ..core.audit import AuditLogger
from ..core.circuit_breaker import CircuitBreaker
from ..core.types import Action, Context, Stage
from ..pipeline import Pipeline, _to_text

logger = logging.getLogger("safetynet.adapters.langgraph")

try:  # pragma: no cover - exercised only when langgraph is installed
    from langgraph.graph import END, StateGraph

    AVAILABLE = True
except Exception:  # noqa: BLE001
    AVAILABLE = False
    END = None  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]


def build_state_graph(pipeline: Pipeline):
    """Compile the guarded pipeline into a LangGraph app.

    The graph state is a dict carrying the rolling input, accumulated node results, breaker, and
    audit logger. Each agent becomes a node that runs PRE gate -> agent -> POST gate, and a
    conditional edge halts the graph if the breaker tripped.
    """
    if not AVAILABLE:
        raise ImportError(
            "langgraph is not installed. Install the optional extra: pip install '.[langgraph]'"
        )

    graph = StateGraph(dict)
    agents = pipeline.agents

    def make_node(agent):
        gate = pipeline.gates[agent.node_id]

        def _node(state: dict) -> dict:
            context: Context = state["context"]
            breaker: CircuitBreaker = state["breaker"]
            audit: AuditLogger = state["audit"]
            current_input: str = state["current_input"]

            pre_action = Action(node_id=agent.node_id, kind=agent.kind, payload=current_input)
            pre = gate.evaluate(pre_action, context, Stage.PRE)
            state["results"].append(pre)
            halt = breaker.observe(pre)
            audit.record(pre, input_payload=current_input, output_payload=None, breaker_state=breaker.state())
            if halt:
                state["halted"] = True
                return state

            output = agent.run(pre_action, context)
            state["outputs"][agent.node_id] = output
            output_text = output if isinstance(output, str) else _to_text(output)

            post_action = Action(node_id=agent.node_id, kind=agent.kind, payload=output_text)
            post = gate.evaluate(post_action, context, Stage.POST)
            post.output = output
            state["results"].append(post)
            halt = breaker.observe(post)
            audit.record(post, input_payload=current_input, output_payload=output, breaker_state=breaker.state())
            if halt:
                state["halted"] = True
                return state

            state["current_input"] = output_text
            return state

        return _node

    for agent in agents:
        graph.add_node(agent.node_id, make_node(agent))

    graph.set_entry_point(agents[0].node_id)

    def route(state: dict, _next_id: str):
        return END if state.get("halted") else _next_id

    for i, agent in enumerate(agents):
        if i + 1 < len(agents):
            nxt = agents[i + 1].node_id
            graph.add_conditional_edges(agent.node_id, lambda s, n=nxt: route(s, n), {END: END, nxt: nxt})
        else:
            graph.add_edge(agent.node_id, END)

    return graph.compile()
