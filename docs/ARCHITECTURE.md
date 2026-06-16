# Architecture

SafetyNet is an **AI Control** layer: it forces safety via external constraints rather than
trusting an aligned model. It is a **security gateway** that wraps external agents — it does not
generate content. The position (governance outside the agent) follows *From Craft to Constitution*
(arXiv:2510.13857) and *Toward a Safe Internet of Agents* (arXiv:2512.00520).

```
                       ┌──────────────────────────────────────────────────────┐
   client  ──prompt──► │  SafetyNet gateway (GuardedAgent / server)            │
                       │                                                        │
                       │  [PRE]  scanners + ethics  ──BLOCK?─► refuse (no call) │
                       │    │ allow                                             │
                       │    ▼                                                   │
                       │  AgentClient.invoke() ───HTTP───►  external agent      │
                       │    │                              (NeMo/LangGraph/…)   │
                       │    ▼ response                                          │
                       │  [POST] scanners + ethics  ──BLOCK?─► withhold output  │
                       │  circuit breaker · JSONL audit · tracer                │
   client ◄─guarded──  └──────────────────────────────────────────────────────┘
```

## Components

| Component | Module | Responsibility |
|---|---|---|
| Shared types | `core/types.py` | `Decision`, `band()`, `Verdict`, `Action`, `Context`, `NodeResult`, `Stage` |
| Policy | `core/policy.py` | Load + validate YAML, normalize weights, compute `policy_hash` |
| Ethics engine | `ethics/` | Pluggable frameworks + stance-based aggregator |
| Scanners | `scanners/` | Content / IP / injection / structure / image checks (pluggable backends) |
| Gate | `core/gate.py` | Run scanners + ethics at PRE/POST; fail-closed; strictest combine |
| Circuit breaker | `core/circuit_breaker.py` | Per-run cumulative risk; unconditional halt on BLOCK |
| Audit | `core/audit.py` | JSONL decision log, content referenced by sha256 |
| Tracing | `core/tracing.py` | Optional observability (NullTracer default; LangfuseTracer) |
| Agent clients | `clients/` | Transport to external agent REST endpoints (+ offline stub) |
| Guard | `guard.py` | `GuardedAgent`: PRE → call client → POST, around breaker/audit/tracer |
| Gateway | `server/app.py` | FastAPI service exposing the guard over HTTP |

## What SafetyNet does NOT contain

No image/video/script generators, no diffusion or LLM inference. Those are **external agents**
the operator runs as Docker containers (see [INTEGRATIONS.md](INTEGRATIONS.md)). SafetyNet only
inspects prompts and responses and decides allow/flag/block.

## Gate stages

- **PRE** — evaluate the request before the agent is called. A BLOCK refuses with no upstream
  call (no spend, no exposure).
- **POST** — evaluate the agent's response (text, and any media bytes carried in `metadata`).
  A BLOCK withholds the output.

(TrustAgent's *in-planning* stage — intercepting mid-generation — is not applicable here: the
external agent is a black box reached over a single request/response, so the audit `stage` field
is `pre|post`.)

## Circuit breaker semantics

- In-memory, scoped to a single `run_id`; never persists across calls.
- A `BLOCK` (deontic veto or scanner hard block) halts **immediately and unconditionally**.
- A `FLAG` adds `1 - score` to cumulative risk; crossing `cumulative_risk_threshold` halts.

## Where the scanners' real models plug in

Each scanner delegates to a pluggable backend (lazy/optional). Defaults are stdlib; real
backends are documented in [CONCEPTS.md](CONCEPTS.md):

- content safety → LlamaGuard/ShieldGemma (`[guard]`) or Claude judge (`[anthropic]`)
- copyright → GoG embedding similarity (`[embeddings]`)
- prompt injection → PromptGuard 2 (`[guard]`)
- image moderation → Azure Content Safety (`[vision-azure]`) / AWS Rekognition (`[vision-aws]`) / local NSFW (`[guard]`)

## Deferred

- Full declarative policy DSL; additional ethical frameworks (Virtue, Care).
- Streaming/SSE proxying for token-level response guarding.
- Image-level CLIP copyright-reproduction scoring (arXiv:2403.12052) via a CLIP vision backend.
