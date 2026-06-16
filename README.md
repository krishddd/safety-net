# SafetyNet — a safety net for generative AI agents

[![CI](https://github.com/krishddd/safety-net/actions/workflows/ci.yml/badge.svg)](https://github.com/krishddd/safety-net/actions/workflows/ci.yml)

SafetyNet is a **deterministic, rule-based ethical orchestration layer** that sits *outside*
generative agents and intercepts every node of a generative media pipeline (script → image → video):

```
Script Agent (LLM)  ──►  Image Agent (diffusion)  ──►  Video Agent (diffusion)
        │                        │                            │
   pre/post gate            pre/post gate                pre/post gate
        └──────────── SafetyNet layer: ethics engine · circuit breaker · audit ───────────┘
```

It operates in the **AI Control** paradigm — safety is forced by external constraints, not
hoped for from a well-aligned model. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## The differentiator: a configurable ethics engine

Operators declare a *moral stance* in YAML. Frameworks are pluggable evaluators sharing one
interface; ship today are **Deontology** (inviolable duties) and **Consequentialism** (outcome
utility). The default `deontology_veto` stance lets a duty breach **arrest** a favorable
consequentialist score — "the ends do not justify the means":

```yaml
ethics:
  stance: deontology_veto        # deontology_veto | weighted | strictest
  frameworks:
    deontology:       { enabled: true, weight: 0.5, duties: [...] }
    consequentialism: { enabled: true, weight: 0.5, harm_threshold: 0.5 }
```

A single `band(score)` helper is the sole authority mapping a continuous safety score to a
`BLOCK / FLAG / ALLOW` decision, so categorical and numeric views never disagree. Full
semantics + worked example: [`docs/ETHICS_ENGINE.md`](docs/ETHICS_ENGINE.md).

## Quickstart

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows; use bin/activate on *nix
pip install -e ".[dev]"

pytest                              # run the test suite
python examples/run_pipeline.py        # benign run passes; adversarial run is halted
```

The example prints a per-node decision trace and writes a JSONL audit log to
`output/audit-<run_id>.jsonl`. Operational logs go to `logs/safetynet.log`.

## Layout

```
src/safetynet/
  core/        types (band/Verdict/Action/Context), policy loader, gate, circuit_breaker, audit, logging
  ethics/      base interface, deontology, consequentialism, aggregator (stances), engine
  scanners/    content_safety, copyright, prompt_injection, character_bible (stdlib stubs)
  agents/      script/image/video stubs behind a common interface
  adapters/    langgraph_adapter (optional dependency)
  pipeline.py  framework-agnostic wiring + build_default_pipeline()
policies/      default.yaml, character_bible.yaml
examples/      run_pipeline.py, run_benchmark.py
tests/         ethics, gate, circuit_breaker, scanners, policy, pipeline
docs/          ARCHITECTURE, ETHICS_ENGINE, THREAT_MODEL, CONCEPTS
```

## Design guarantees

- **Fail-closed** — a scanner/framework that raises becomes a `BLOCK` (configurable to `FLAG`),
  never a silent `ALLOW`.
- **Unconditional halt on hard block** — a `BLOCK` short-circuits the circuit breaker
  immediately, even at zero accumulated risk; only `FLAG`s feed the cumulative threshold.
- **Reconstructable audit** — every node decision is logged with the `policy_hash` in effect and
  content referenced by sha256 (EU AI Act Art. 13/14; NIST AI RMF).

## Optional integrations (install extras)

Everything above runs with **no GPU or API keys**. These extras wire in real models /
frameworks behind the same interfaces — all imports are lazy and fail-closed, so the core
stays dependency-light.

| Extra | Install | Adds |
|---|---|---|
| `guard` | `pip install '.[guard]'` | `TransformersGuardBackend` — local LlamaGuard/ShieldGemma behind `ContentSafetyScanner` |
| `anthropic` | `pip install '.[anthropic]'` | `AnthropicModerationBackend` — Claude LLM-as-judge moderation (needs `ANTHROPIC_API_KEY`) |
| `langgraph` | `pip install '.[langgraph]'` | LangGraph `StateGraph` adapter |
| `nemo` | `pip install '.[nemo]'` | NeMo Guardrails custom-action adapter |
| `crewai` | `pip install '.[crewai]'` | CrewAI task-guardrail adapter |

Select a moderation backend in policy: `content_safety: { backend: transformers, model_id: ... }`
or inject one directly: `ContentSafetyScanner(backend=AnthropicModerationBackend())`.

## Benchmark harness

Evaluate SafetyNet's detection against labeled agent-safety datasets (R-Judge,
Agent-SafetyBench, or any JSONL). A small offline sample ships in the repo:

```bash
python examples/run_benchmark.py                 # runs on the bundled sample
python -m safetynet.benchmark --dataset r-judge.jsonl --format rjudge   # real dataset
```

It reports accuracy / precision / recall / F1 and a confusion matrix, with a `--block-only`
mode to measure refusals vs. mere flags. See [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

## Status

Phase 1 + first integrations. Real moderation backends (transformers/Anthropic), LangGraph /
NeMo / CrewAI adapters, and the benchmark harness are in place; copyright/injection scanners
still ship as stdlib stubs, and Langfuse tracing + a full policy DSL remain documented swap-in
points — see [`docs/CONCEPTS.md`](docs/CONCEPTS.md) and
[`SafetyNet_Research_Reference.md`](SafetyNet_Research_Reference.md).

## License

Apache-2.0. See [`LICENSE`](LICENSE).
