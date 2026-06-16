# Threat Model

Seeded from the **OWASP Top 10 for LLM Applications (2025)** and the full-stack-safety survey
*A Comprehensive Survey in LLM(-Agent) Full Stack Safety: Data, Training and Deployment*
(arXiv:2504.15585, 800+ references). This enumerates the failure classes SafetyNet must address
in a generative media pipeline (script → image → video) and where each defense lives.

## Assets

- **Brand/IP integrity** — generated frames must not reproduce protected third-party IP.
- **Character-bible fidelity** — characters and tone must match the project bible.
- **Audience safety** — no harmful content for the (often young) target audience.
- **Pipeline integrity** — no node may be hijacked to corrupt downstream nodes.

## Threats → defenses

| # | Threat (OWASP LLM / agent) | Where it hits | SafetyNet defense |
|---|---|---|---|
| 1 | **Prompt injection** (direct & indirect) | Script/Image/Video input | `PromptInjectionScanner` (→ LlamaFirewall PromptGuard) at PRE gate |
| 2 | **Insecure output handling** | Script→Image hand-off | POST-stage gate re-scans every node output before it becomes the next input |
| 3 | **Sensitive-info / IP disclosure** | Image/Video prompts | `CopyrightScanner` (→ GoG arXiv:2503.16171 / CopyJudge arXiv:2502.15278) |
| 4 | **Harmful content generation** | All nodes | `ContentSafetyScanner` (→ LlamaGuard/ShieldGemma) + consequentialism harm model |
| 5 | **Excessive agency / out-of-policy acts** | Any agent | Deontology duties + `deontology_veto` stance (least-privilege intent) |
| 6 | **Multi-agent cascade failure** | Script → Image → Video | Circuit breaker halts before downstream nodes (NetSafe / G-Safeguard) |
| 7 | **Misalignment / goal drift** | Across the trace | Cumulative-risk circuit breaker over the run's accumulated FLAGs |
| 8 | **Policy bypass / silent failure** | Scanner/framework error | **Fail-closed**: errors become BLOCK (or configured FLAG), never silent ALLOW |
| 9 | **Non-repudiation / audit gaps** | Compliance | JSONL audit log with `policy_hash` + content hashes (EU AI Act, NIST AI RMF) |
| 10 | **Config tampering / drift** | Policy file | `policy_hash` records the exact resolved rules; runs are reconstructable |

## Trust boundaries

- The agents are **untrusted**: SafetyNet never relies on an agent to police itself.
- The policy file is **trusted input**, but validated (schema + stance + fail_mode checks) and
  hashed so any change is detectable in the audit trail.
- Scanners/frameworks are **fail-closed**: a crash is treated as the unsafe outcome.

## Residual risk (Phase 1)

- Stub scanners are keyword/similarity heuristics — they catch the documented trigger classes but
  are not production detectors. Swap in the referenced models before any real deployment.
- No in-execution (mid-generation) monitoring yet; streaming attacks that only manifest mid-stream
  are out of scope until the `in` stage lands (see [ARCHITECTURE.md](ARCHITECTURE.md)).
- Adversarial robustness of the stubs is untested; use the benchmarks in
  [CONCEPTS.md](CONCEPTS.md) (R-Judge, Agent-SafetyBench, the copyright benchmark) before trusting.
