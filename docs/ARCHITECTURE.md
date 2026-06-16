# Architecture

SafetyNet is an **AI Control** layer: it forces safety via external constraints rather than
trusting an aligned model. Governance lives in the orchestration layer, outside the agents — the
position argued in *From Craft to Constitution* (arXiv:2510.13857) and *Toward a Safe Internet of
Agents* (arXiv:2512.00520).

```
                ┌──────────────────────────────────────────────┐
                │            SAFETYNET LAYER                     │
                │  Policy · Ethics Engine · Circuit Breaker · Audit │
                └──────────────────────────────────────────────┘
   pre │ post gate wraps every node (TrustAgent pre/post stages, arXiv:2402.01586)
        ▼              ▼                     ▼
 ┌─────────────┐ ┌──────────────┐   ┌──────────────┐
 │ Script Agent│→│ Image Agent  │ → │ Video Agent  │
 └─────────────┘ └──────────────┘   └──────────────┘
```

## Components

| Component | Module | Responsibility |
|---|---|---|
| Shared types | `core/types.py` | `Decision`, `band()`, `Verdict`, `Action`, `Context`, `NodeResult`, `Stage` |
| Policy | `core/policy.py` | Load + validate YAML, normalize weights, compute `policy_hash` |
| Ethics engine | `ethics/` | Pluggable frameworks + stance-based aggregator |
| Scanners | `scanners/` | Content/IP/injection/structure checks (stdlib stubs) |
| Gate | `core/gate.py` | Run scanners + ethics at PRE/POST; fail-closed; strictest combine |
| Circuit breaker | `core/circuit_breaker.py` | Per-run cumulative risk; unconditional halt on BLOCK |
| Audit | `core/audit.py` | JSONL decision log, content referenced by sha256 |
| Pipeline | `pipeline.py` | Framework-agnostic wiring of nodes/gates/breaker/audit |
| LangGraph adapter | `adapters/langgraph_adapter.py` | Optional `StateGraph` wrapper |

## Gate stages — why two, not three

TrustAgent describes pre-planning, in-planning, and post-planning interception. SafetyNet's
gate implements **`pre`** (evaluate the input before the node runs) and **`post`** (evaluate the
output after). Phase-1 stub agents return their output in one shot, so there is nothing to
intercept mid-generation; the audit schema's `stage` field is therefore `pre|post` only. **True
in-execution monitoring is explicitly deferred** to a later phase with streaming-capable agents,
where token-level rails (e.g. NeMo Colang) would slot into an `in` stage.

## Circuit breaker semantics

- State is **in-memory and scoped to a single `run_id`** — a fresh breaker per pipeline run; risk
  never persists across runs.
- A `BLOCK` (deontic veto or scanner hard block) halts **immediately and unconditionally**.
- A `FLAG` adds `1 - score` to cumulative risk; crossing `cumulative_risk_threshold` halts.
- Halting before a downstream node mitigates **topological cascade risk** (NetSafe arXiv:2410.15686;
  G-Safeguard arXiv:2502.11127) — a compromised upstream node never reaches the more expensive
  image/video stages.

## Data flow per node

```
input ─► Gate.PRE (scanners + ethics, strictest) ─► breaker.observe ─► audit
          │ halt? ─► stop
          ▼ pass
        agent.run ─► output ─► Gate.POST ─► breaker.observe ─► audit
          │ halt? ─► stop
          ▼ pass
        output becomes next node's input
```

## Done since Phase 1

- **Real moderation backends** behind `ContentSafetyScanner` — `TransformersGuardBackend`
  (LlamaGuard/ShieldGemma) and `AnthropicModerationBackend` (LLM-as-judge), policy-selectable,
  lazy/optional, fail-closed. See `scanners/moderation.py`.
- **NeMo Guardrails and CrewAI adapters** alongside the LangGraph one (`adapters/`).
- **Benchmark harness** (R-Judge / Agent-SafetyBench / generic JSONL) with metrics + CLI
  (`benchmark/`, [BENCHMARKS.md](BENCHMARKS.md)).

## Deferred (follow-up phases)

- Real diffusion / cloud-vision moderation for the image/video nodes; embedding-based copyright
  (GoG) and PromptGuard injection models behind their existing scanner interfaces.
- Langfuse-backed tracing; the copyright-reproduction benchmark (arXiv:2403.12052).
- In-execution (`in`) stage for streaming agents; full declarative policy DSL; Virtue/Care frameworks.
