# SynemaGuard — a safety net for generative AI agents

[![CI](https://github.com/krishddd/safety-net/actions/workflows/ci.yml/badge.svg)](https://github.com/krishddd/safety-net/actions/workflows/ci.yml)

SynemaGuard is a **deterministic, rule-based ethical orchestration layer** that sits *outside*
generative agents and intercepts every node of a "Cartoon Movie" pipeline:

```
Script Agent (LLM)  ──►  Image Agent (diffusion)  ──►  Video Agent (diffusion)
        │                        │                            │
   pre/post gate            pre/post gate                pre/post gate
        └──────────── SynemaGuard layer: ethics engine · circuit breaker · audit ───────────┘
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
python examples/run_cartoon_movie.py   # benign run passes; adversarial run is halted
```

The example prints a per-node decision trace and writes a JSONL audit log to
`output/audit-<run_id>.jsonl`. Operational logs go to `logs/synemaguard.log`.

## Layout

```
src/synemaguard/
  core/        types (band/Verdict/Action/Context), policy loader, gate, circuit_breaker, audit, logging
  ethics/      base interface, deontology, consequentialism, aggregator (stances), engine
  scanners/    content_safety, copyright, prompt_injection, character_bible (stdlib stubs)
  agents/      script/image/video stubs behind a common interface
  adapters/    langgraph_adapter (optional dependency)
  pipeline.py  framework-agnostic wiring + build_default_pipeline()
policies/      default.yaml, character_bible.yaml
examples/      run_cartoon_movie.py
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

## Status

Phase 1: dependency-light skeleton with **stubbed but pluggable** scanners/generators (runs with
no GPU or API keys). Real models (LlamaGuard, GoG/CopyJudge, Azure Content Safety), NeMo/CrewAI
adapters, Langfuse tracing, and a full policy DSL are documented swap-in points — see
[`docs/CONCEPTS.md`](docs/CONCEPTS.md) and [`SynemaGuard_Research_Reference.md`](SynemaGuard_Research_Reference.md).

## License

Apache-2.0. See [`LICENSE`](LICENSE).
