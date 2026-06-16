# Threat Model

Seeded from the **OWASP Top 10 for LLM Applications (2025)** and the full-stack-safety survey
*A Comprehensive Survey in LLM(-Agent) Full Stack Safety: Data, Training and Deployment*
(arXiv:2504.15585, 800+ references). This enumerates the failure classes SafetyNet must address
when SafetyNet guards external generative agents (a script/image/video chain reached over HTTP)
and where each defense lives. SafetyNet sits at each agent call — guarding the request and the
response — and never trusts the agent to police itself.

## Assets

- **Brand/IP integrity** — generated frames must not reproduce protected third-party IP.
- **Character-bible fidelity** — characters and tone must match the project bible.
- **Audience safety** — no harmful content for the (often young) target audience.
- **Pipeline integrity** — no node may be hijacked to corrupt downstream nodes.

## Threats → defenses

| # | Threat (OWASP LLM / agent) | Where it hits | SafetyNet defense |
|---|---|---|---|
| 1 | **Prompt injection** (direct & indirect) | request (any message) | `PromptInjectionScanner` (→ PromptGuard) at PRE; the gateway guards the **whole** message list |
| 1b | **Guardrail evasion** (homoglyph / zero-width / tag / leet / base64) | request & response | `scanners/normalize.py` folds obfuscation away before matching (arXiv:2504.11168) |
| 2 | **Insecure output handling** | agent response | POST-stage gate re-scans the agent reply before it is returned |
| 3 | **Sensitive-info / IP disclosure** | request & response | `CopyrightScanner` (→ GoG/CopyJudge) + `PIIScanner` (secrets→BLOCK, PII→FLAG) |
| 4 | **Harmful content generation** | All nodes | `ContentSafetyScanner` (→ LlamaGuard/ShieldGemma) + consequentialism harm model |
| 5 | **Excessive agency / out-of-policy acts** | Any agent | Deontology duties + `deontology_veto` stance (least-privilege intent) |
| 6 | **Multi-agent cascade failure** | chained external agents | Circuit breaker halts before the next guarded call (NetSafe / G-Safeguard) |
| 7 | **Misalignment / goal drift** | Across the trace | Cumulative-risk circuit breaker over the run's accumulated FLAGs |
| 8 | **Policy bypass / silent failure** | scanner/framework error, **upstream agent error** | **Fail-closed**: scanner errors → BLOCK/FLAG; an upstream transport/HTTP error → BLOCK at the `upstream` stage, never silent ALLOW |
| 9 | **Non-repudiation / audit gaps** | Compliance | JSONL audit log with `policy_hash` + content hashes (EU AI Act, NIST AI RMF) |
| 10 | **Config tampering / drift** | Policy file | `policy_hash` records the exact resolved rules; runs are reconstructable |

## Trust boundaries

- The agents are **untrusted**: SafetyNet never relies on an agent to police itself.
- The policy file is **trusted input**, but validated (schema + stance + fail_mode checks) and
  hashed so any change is detectable in the audit trail.
- Scanners/frameworks are **fail-closed**: a crash is treated as the unsafe outcome.

## Residual risk

- Default scanners are keyword/similarity heuristics hardened with obfuscation folding. They catch
  the documented character-injection classes, but **semantic** paraphrase/adversarial-ML attacks
  that preserve meaning without trigger terms need a model backend — enable `[guard]` (PromptGuard /
  LlamaGuard) and `[embeddings]` (GoG) before any real deployment.
- Normalization covers the common evasions (homoglyph, zero-width, tag/emoji smuggling, full-width,
  diacritics, leetspeak, intra-letter spacing, single-layer Base64). Nested multi-layer encodings
  and novel confusables outside the curated map can still slip the keyword stubs.
- No mid-generation / streaming-response monitoring yet (the proxy guards the full response once
  received). Token-level/SSE guarding is deferred.
- PII detection is regex-based (conservative, Luhn-checked cards); swap in Presidio / cloud DLP for
  coverage. Validate with the benchmarks in [CONCEPTS.md](CONCEPTS.md) before trusting in production.
