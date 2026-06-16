# Concepts — research grounding mapped to components

This maps each SynemaGuard component to the tool/paper that backs it. The full survey is in
[`../SynemaGuard_Research_Reference.md`](../SynemaGuard_Research_Reference.md). Every citation
below was verified to resolve and to match its described use (see "Citation notes" at the end).

## Paradigm

| Concept | Source | In SynemaGuard |
|---|---|---|
| AI Control vs AI Alignment | *From Craft to Constitution* (arXiv:2510.13857) | Governance sits **outside** agents, in the orchestration layer |
| Deterministic policy vs probabilistic execution | *Toward a Safe Internet of Agents* (arXiv:2512.00520) | The gate/breaker are deterministic; agents stay probabilistic |
| Policy-to-practice gap | *Policy-as-Prompt* (arXiv:2509.23994) | YAML policy → runtime constraints; future declarative DSL |
| Agent Constitution (pre/in/post) | *TrustAgent* (arXiv:2402.01586) | PRE/POST gate stages (in-stage deferred) |

## Gate & scanners

| Component | Backing tool/paper | Swap-in note |
|---|---|---|
| `ContentSafetyScanner` | LlamaGuard 4 / NeMoGuard-8B / ShieldGemma | Replace keyword stub with classifier I/O |
| `CopyrightScanner` | GoG (arXiv:2503.16171), CopyJudge (arXiv:2502.15278) | Replace Jaccard stub with embedding sim + LVLM judge |
| `PromptInjectionScanner` | LlamaFirewall PromptGuard 2 (arXiv:2505.03574) | Replace pattern list with PromptGuard model |
| `CharacterBibleScanner` | Guardrails AI (RAIL), NeMo Colang | Replace structural stub with schema/rail validation |

## Ethics engine

| Concept | Source | In SynemaGuard |
|---|---|---|
| Deontological / least-privilege constraints | *ProgEnt* (arXiv:2504.11703), *AgentGuardian* | `DeontologyFramework` duties + `deontology_veto` |
| Consequentialist outcome weighing | classical normative ethics | `ConsequentialismFramework` net-harm model |
| Configurable stance | (novel) | `Aggregator` stances; see [ETHICS_ENGINE.md](ETHICS_ENGINE.md) |

## Circuit breaker & multi-agent governance

| Concept | Source | In SynemaGuard |
|---|---|---|
| Per-node monitoring / corrupted-node isolation | *Securing MAS via Node Contribution Backpropagation* (arXiv:2510.19420, ICML 2026) | Per-node `observe()` before downstream propagation |
| Topological cascade risk | *NetSafe* (arXiv:2410.15686), *G-Safeguard* (arXiv:2502.11127, ACL 2025) | Halt-before-downstream stops cascades |
| Trace-level safety contracts | Invariant Labs | Cumulative-risk breaker over the run trace |
| Audit / observability | Langfuse | JSONL audit log (Langfuse is the future backend) |

## Governance & compliance

| Standard | In SynemaGuard |
|---|---|
| EU AI Act Art. 13/14 (traceability, human oversight) | `policy_hash` + per-node audit; `human_review_on_flag` |
| NIST AI RMF / NIST.AI.600-1 | Continuous logging, adversarial-test hooks |
| OWASP Top 10 for LLM Apps (2025) | Enumerated in [THREAT_MODEL.md](THREAT_MODEL.md) |

## Benchmarks (for future validation)

R-Judge (arXiv:2401.10019), Agent-SafetyBench (arXiv:2412.14470), Copyright Infringement
Benchmark (arXiv:2403.12052). Not wired in Phase 1; targeted for the evaluation harness.

## Citation notes (from the verification pass)

- **CopyJudge** (2502.15278) and **NetSafe** (2410.15686): titles and descriptions confirmed accurate.
- **G-Safeguard**: arXiv ID is **2502.11127** (ACL 2025) — supplied here (was absent in the survey).
- **Full-stack survey** (2504.15585): real title is *"A Comprehensive Survey in LLM(-Agent) Full
  Stack Safety: Data, Training and Deployment"*; it cites **800+** papers (not 900+).
- **arXiv:2510.19420**: real title is *"Securing Multi-Agent Systems Against Corruptions via Node
  Contribution Backpropagation"* (ICML 2026). Its mechanism is **node-contribution backpropagation**
  to isolate corrupted agents — not "scoring each node's output against expected behavior". We use
  it as conceptual support for per-node observation, described accurately above.
