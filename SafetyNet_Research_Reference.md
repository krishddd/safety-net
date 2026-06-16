# SafetyNet Research Reference
## Comprehensive Survey: AI Governance Layers, Safety Guardrails & Deontological Agent Constraints

> **Purpose:** This document maps every relevant tool, open-source framework, arXiv paper, benchmark, and enterprise product that is directly applicable to building SafetyNet — a deterministic, rule-based ethical orchestration layer sitting atop generative AI pipelines (LLMs + Diffusion models) for script, image, and video generation.

---

## TABLE OF CONTENTS

1. [The Conceptual Foundation — Why SafetyNet is Novel](#1-conceptual-foundation)
2. [Open-Source Tools & Frameworks](#2-open-source-tools)
3. [Enterprise / Paid Tools](#3-enterprise-paid-tools)
4. [Core arXiv Papers — Agent Safety & Guardrails](#4-arxiv-agent-safety)
5. [Core arXiv Papers — Copyright & IP Protection in Diffusion Models](#5-arxiv-copyright-diffusion)
6. [Core arXiv Papers — Multi-Agent Governance & Circuit Breakers](#6-arxiv-multi-agent)
7. [Safety Benchmarks & Evaluation Datasets](#7-benchmarks)
8. [Governance Standards & Regulatory Frameworks](#8-governance-standards)
9. [SafetyNet Architecture Mapping](#9-architecture-mapping)

---

## 1. CONCEPTUAL FOUNDATION

SafetyNet's core tension is described precisely in the paper *"Toward a Safe Internet of Agents"* (arXiv:2512.00520):

> *"Guardrails must enforce safety guarantees that hold even against an adversarial model. This creates the fundamental architectural tension between **deterministic policy** (strict rules) and **probabilistic execution** (flexible reasoning)."*

The field distinguishes two paradigms:

| Paradigm | Approach | Failure Mode |
|---|---|---|
| **AI Alignment** | Train the model to *want* to be safe | Alignment can drift; no external guarantee |
| **AI Control (SafetyNet's approach)** | Force the system to be safe via external constraints | Must be architecturally sound; cannot rely on the model |

SafetyNet operates in the **AI Control** paradigm — analogous to how a type system in a compiler enforces correctness regardless of programmer intent.

The **policy-to-practice gap** (arXiv:2509.23994) is the central problem: high-level human-readable rules must become low-level machine-enforceable constraints at every node in the pipeline. This is exactly what SafetyNet's Circuit Breakers address.

---

## 2. OPEN-SOURCE TOOLS & FRAMEWORKS

### 2.1 Orchestration-Level Guardrails

#### NVIDIA NeMo Guardrails
- **Repo:** https://github.com/NVIDIA-NeMo/Guardrails
- **Stars:** 4,200+
- **License:** Apache 2.0
- **What it does:** Programmable guardrails for LLM-based applications using a custom scripting language called **Colang**. Lets developers define topical rails (stay on topic), safety rails (block harmful content), and security rails (prevent jailbreaks). Runtime is inspired by dialogue management, independent of the underlying LLM.
- **Relevance to SafetyNet:** Direct analog for the Script Agent layer. Colang scripts can encode your character bible rules and narrative constraints. Integrates natively with **LangChain/LangGraph**.
- **Key features:**
  - Input/output moderation
  - Jailbreak detection
  - Hallucination rail for RAG
  - Fact-checking rail
  - Evaluation tool (`nemoguardrails evaluate`)
- **Paper:** *"NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications with Programmable Rails"* (NVIDIA Research, 2023)

#### Guardrails AI
- **Repo:** https://github.com/guardrails-ai/guardrails
- **Stars:** 4,500+
- **License:** Apache 2.0
- **What it does:** Declarative output validation framework. Defines **RAIL (Reliable AI Language)** specs — XML/Python schemas that describe exactly what a valid LLM output looks like. If output violates the spec, it triggers re-asking or correction loops.
- **Relevance to SafetyNet:** Perfect for the Script Agent's structural rules. Can validate that a script output contains required fields (scene number, character names from the bible, no prohibited phrases), enforcing schema compliance rather than relying on the model to comply.
- **Key features:**
  - Composable validators (pydantic-style)
  - Input AND output scanning
  - Guardrails Hub (community validators)
  - Re-ask / correction loop on violation

#### LlamaFirewall (Meta)
- **Repo:** https://github.com/meta-llama/PurpleLlama/tree/main/LlamaFirewall
- **Paper:** arXiv:2505.03574 (May 2025)
- **License:** Open source (Meta)
- **What it does:** A unified guardrail system for **agentic AI** specifically. Provides PromptGuard (prompt injection detection), CodeShield (unsafe code generation), and AlignmentCheck (agent alignment monitoring). Purpose-built for multi-step agent pipelines, not just single LLM calls.
- **Relevance to SafetyNet:** The most architecturally relevant open-source tool. AlignmentCheck monitors whether agent actions remain aligned with intended goals across multi-step workflows — directly applicable to your circuit breaker concept.
- **Key features:**
  - PromptGuard 2 for injection attacks
  - Agent-level alignment scoring
  - CodeShield for unsafe code
  - Designed for agentic pipelines (not just chat)

#### LLM Guard (Protect AI)
- **Repo:** https://github.com/protectai/llm-guard
- **Stars:** 1,200+
- **License:** MIT
- **What it does:** Input/output security scanning library. Modular scanners for: toxicity, ban topics, prompt injection, PII detection, code injection, relevance, sensitive data.
- **Relevance to SafetyNet:** Can be composed as individual scanner modules at each pipeline node — one scanner per rule category in your character bible or visual safety spec.
- **Key features:**
  - Fully modular (add/remove scanners)
  - Can run locally (no external API call)
  - Low latency (designed for production)

#### Invariant Labs Safety Framework
- **Repo:** https://github.com/invariantlabs-ai/invariant
- **License:** Open source
- **What it does:** Provides formal safety contracts for LLM agents. You write **safety policies** in a Python-like DSL, and the system enforces them at the agent trace level. Focuses on detecting unsafe patterns across multi-step traces, not just single inputs.
- **Relevance to SafetyNet:** The "trace-level" enforcement model is exactly what circuit breakers need — the ability to halt a workflow when cumulative behavior crosses a threshold.

#### OpenGuardrails
- **Paper:** arXiv:2510.19169 (2025)
- **License:** Open source
- **What it does:** Context-aware guardrails with multilingual safety, manipulation detection, and data-leak prevention. Benchmarked to outperform LlamaGuard, WildGuard, and Qwen3Guard on multilingual safety.
- **Relevance:** Strongest open-source baseline for the output moderation layer.

---

### 2.2 Input/Output Classifier Models

| Model | Creator | arXiv | Best For |
|---|---|---|---|
| **LlamaGuard 3 / 4** | Meta | arXiv:2312.06674 | Content safety classification (I/O) |
| **NeMoGuard-8B ContentSafety** | NVIDIA | — | Fast content safety with JSON output |
| **ShieldGemma-9B / 27B** | Google | — | General safety; structured output |
| **WildGuard-7B** | AI2 | — | Instruction-following safety |
| **Granite Guardian** | IBM | — | Enterprise safety inspection |
| **Qwen3Guard** | Alibaba | arXiv:2510.14276 | Multilingual + high accuracy |

> **SafetyNet Recommendation:** Run **LlamaGuard 4** or **NeMoGuard-8B** as the classifier at the output of both the Script Agent and Visual Generation Agents. These are fast, local, and can be fine-tuned on your character bible vocabulary.

---

### 2.3 Observability & Tracing

#### Langfuse
- **URL:** https://langfuse.com
- **License:** Open source (self-host) / Cloud
- **What it does:** LLM observability, tracing, and evaluation. Each pipeline step is traced; security scanners (LLM Guard, NeMo, Lakera) can be integrated into trace steps.
- **Relevance:** Critical for SafetyNet's audit log requirement. Every node decision — pass/block/halt — is logged and traceable.

#### Galileo Agent Control
- **URL:** https://www.rungalileo.io
- **License:** Open source (Apache 2.0) for Agent Control
- **What it does:** Write behavioral policies once, enforce them across all agent deployments. Integrates with LangChain, CrewAI, OpenAI Agents SDK. Raised $68M (Series B, 2024).
- **Relevance:** Their Luna small language models enable guardrailing on **100% of production traffic** (not sampling) — critical for deterministic enforcement.

---

## 3. ENTERPRISE / PAID TOOLS

### 3.1 Runtime Security Layers

| Tool | Company | Key Capability | Pricing Model |
|---|---|---|---|
| **Lakera Guard** (acquired by Check Point, Nov 2025) | Lakera/Check Point | Real-time prompt injection, jailbreak, PII, content violation detection. 99.2% accuracy. 50,000+ known attack patterns. | From ~$500/month enterprise |
| **Aporia Guardrails** | Aporia | Prompt injection, data leakage, customizable AI policies. Strong on agentic workflows. | Enterprise contract |
| **Patronus AI** | Patronus | LLM evaluation + hallucination detection. LynxIQ for RAG faithfulness. | Enterprise contract |
| **Calypso AI Moderator** | Calypso AI | Comprehensive LLM security for enterprise. Data loss prevention, IP scanning. | Enterprise contract |
| **Azure AI Content Safety** | Microsoft | Multi-modal (text + image) moderation. Direct integration with Azure OpenAI. | Pay-per-call |
| **AWS Bedrock Guardrails** | Amazon | Managed guardrails for Bedrock agents. Topic denial, PII redaction, grounding checks. | Pay-per-call |
| **Prompt Security** | Prompt Security | Injection protection + AI policy enforcement | Enterprise contract |
| **Lasso Guard** | Lasso Security | LLM Guardian — assessment, threat modeling, behavioral policy | Enterprise contract |

### 3.2 Multi-Modal / Visual Content Safety

| Tool | Company | Key Capability |
|---|---|---|
| **Azure AI Content Safety (Vision)** | Microsoft | Image moderation: violence, sexual content, hate symbols. REST API. |
| **Google Cloud Vision AI / SafeSearch** | Google | Multi-label image safety classification. Integrates into diffusion pipelines. |
| **Amazon Rekognition Content Moderation** | Amazon | Real-time image/video moderation. Anatomical content, violence, IP detection. |
| **Clarifai Moderation** | Clarifai | Fine-tunable content moderation models. Supports custom "unsafe" categories. |
| **HiveModeration** | Hive | Specialized for AI-generated content detection + moderation. |

### 3.3 AI Red Teaming & Adversarial Testing

| Tool | Company | Key Capability |
|---|---|---|
| **Lakera Red** | Lakera/Check Point | Automated red-teaming; simulates attacks before going live |
| **Garak** | NVIDIA | Open-source LLM vulnerability scanner (CLI) |
| **HiddenLayer Model Scanner** | HiddenLayer | ML model supply chain risk; scans weights for backdoors/poisoning |
| **Mindgard** | Mindgard | AI threat modeling + automated pen testing |
| **General Analysis** | General Analysis | Full agentic AI security: prompt injection, RAG poisoning, MCP abuse, tool misuse |

---

## 4. ARXIV PAPERS — AGENT SAFETY & GUARDRAILS

### Foundational Architecture Papers

#### [1] TrustAgent — Agent Constitution Framework
- **arXiv:** 2402.01586 (Feb 2024, published EMNLP Findings 2024)
- **Authors:** Hua et al.
- **Key Insight:** Introduces the **Agent Constitution** — a formal set of safety rules that govern agent behavior at three stages: (1) **pre-planning** (inject safety knowledge before generation), (2) **in-planning** (constrain generation in real time), (3) **post-planning** (inspect output before execution).
- **Direct Relevance:** SafetyNet's three-layer approach (Script → Visual → Circuit Breaker) maps directly to pre/in/post-planning stages. The Agent Constitution concept is the theoretical basis for your character bible enforcement.
- **Link:** https://arxiv.org/abs/2402.01586

#### [2] LlamaFirewall — Open Source Guardrail System for Agents
- **arXiv:** 2505.03574 (May 2025)
- **Authors:** Chennabasappa et al. (Meta)
- **Key Insight:** First open-source guardrail system designed explicitly for **agentic** (multi-step) pipelines rather than single-turn chat. Addresses prompt injection through tool use, indirect injection through retrieved content, and agent alignment drift.
- **Direct Relevance:** Blueprint for SafetyNet's inter-agent communication security. The PromptGuard + AlignmentCheck combination is equivalent to your input gate + circuit breaker.
- **Link:** https://arxiv.org/abs/2505.03574

#### [3] AgentGuardian — Learning Access Control Policies
- **arXiv:** 2601.10440 (2025)
- **Authors:** (from citations in paper)
- **Key Insight:** Frames agent safety as an **access control** problem. Learns policies that govern which agent actions are permitted given the current state. Uses control flow analysis to detect policy violations before execution.
- **Direct Relevance:** Your circuit breaker logic — "halt if an agent deviates from prescribed duty" — is formalized here as access control policy enforcement.
- **Link:** https://arxiv.org/pdf/2601.10440

#### [4] ProgEnt — Programmable Privilege Control for LLM Agents
- **arXiv:** 2504.11703 (Apr 2025)
- **Authors:** Shi et al.
- **Key Insight:** Implements **least-privilege policy** at runtime by validating agent inputs and outputs against formal privilege specs. An agent cannot perform any action not explicitly granted by its privilege specification.
- **Direct Relevance:** Identical to SafetyNet's deontological premise — agents can only do what their rule set explicitly permits, not what they statistically infer is helpful.
- **Link:** https://arxiv.org/abs/2504.11703

#### [5] Policy-as-Prompt — Turning Governance Rules into Guardrails
- **arXiv:** 2509.23994 (Sep 2025)
- **Key Insight:** Bridges the **policy-to-practice gap** — converts high-level human-readable policies into machine-enforceable runtime guardrails. Introduces "just-in-time, contextual security" as opposed to static rule filters.
- **Direct Relevance:** Exactly the engineering challenge SafetyNet must solve: your character bible and visual safety specs are human-readable policies; SafetyNet must translate them to runtime constraints.
- **Link:** https://arxiv.org/pdf/2509.23994

#### [6] Toward a Safe Internet of Agents
- **arXiv:** 2512.00520 (Dec 2024)
- **Key Insight:** Comprehensive architecture for agent safety at network scale. Formalizes the tension between deterministic policy and probabilistic execution. Introduces defense layers: input validation, action sandboxing, output verification, and inter-agent trust management.
- **Direct Relevance:** Full architectural reference for SafetyNet's design. The "guardrail architecture" section (3.5) is essential reading.
- **Link:** https://arxiv.org/pdf/2512.00520

#### [7] From Craft to Constitution — Governance-First Agent Engineering
- **arXiv:** 2510.13857 (Oct 2025)
- **Key Insight:** Argues that agent safety must be an **architectural guarantee**, not a convention. Frameworks like TrustAgent and CrewAI that embed constitutional checks within agent logic are insufficient because governance becomes probabilistic. Proposes **deterministic policy enforcement at the orchestration layer**.
- **Direct Relevance:** This paper is the theoretical manifesto for SafetyNet's deontological approach. Directly validates why SafetyNet sits *outside* the agents (not inside them).
- **Link:** https://arxiv.org/html/2510.13857v1

#### [8] NetSafe — Topological Safety of Multi-Agent Networks
- **arXiv:** 2410.15686 (2024/2025)
- **Authors:** Yu et al.
- **Key Insight:** Studies how safety failures **propagate topologically** through multi-agent networks. Shows that a single compromised node can cascade failures across connected agents.
- **Direct Relevance:** Validates SafetyNet's cascade risk framing. The Script Agent → Visual Agents cascade you identified is a known failure mode with formal characterization here.
- **Link:** https://arxiv.org/abs/2410.15686

#### [9] Hallucination Mitigation using Agentic AI Frameworks
- **arXiv:** 2501.13946 (Jan 2025)
- **Key Insight:** Shows that orchestrating multiple specialized agents with validation checkpoints reduces hallucination rates. Introduces KPIs for hallucination measurement across multi-agent pipelines.
- **Direct Relevance:** Provides metrics for measuring SafetyNet's effectiveness at the Script Agent layer.
- **Link:** https://arxiv.org/pdf/2501.13946

#### [10] Causal Influence Prompting for LLM Agent Safety
- **arXiv:** 2507.00979 (2025)
- **Key Insight:** Uses causal influence diagrams to identify which inputs causally determine unsafe outputs, enabling targeted intervention.
- **Direct Relevance:** Useful for understanding *why* certain script inputs lead to unsafe visual outputs — enabling causal circuit breakers.
- **Link:** https://arxiv.org/pdf/2507.00979

---

## 5. ARXIV PAPERS — COPYRIGHT & IP PROTECTION IN DIFFUSION MODELS

### Critical Papers for the Visual Agent Safety Layer

#### [11] Guardians of Generation (GoG) — Dynamic Copyright Shielding
- **arXiv:** 2503.16171 (Mar 2025)
- **Authors:** RespAI Lab
- **Key Insight:** Model-agnostic, **inference-time** copyright protection — no model retraining. Three components: (1) **Detection Module** — embedding-based similarity check to flag protected IP in prompts, (2) **Prompt Rewriting Module** — LLM rewrites flagged prompts while preserving intent, (3) **Adaptive CFG** — modulates the diffusion sampling trajectory away from infringing content.
- **Works on:** Stable Diffusion 2.1, SDXL, Flux
- **Direct Relevance:** This is the blueprint for SafetyNet's Visual Agent IP protection layer. The three-component architecture can be directly integrated as a pre-diffusion gate.
- **Code:** https://respailab.github.io/gog
- **Link:** https://arxiv.org/abs/2503.16171

#### [12] CopyJudge — Automated Infringement Identification & Mitigation
- **arXiv:** 2502.15278 (Feb 2025)
- **Key Insight:** Uses Large Vision Language Models (LVLMs) as judges to automatically identify infringing prompts. Provides a mitigation strategy that optimizes prompts away from sensitive expressions while preserving non-infringing content. Also explores non-infringing noise vectors in the diffusion latent space.
- **Direct Relevance:** CopyJudge's LVLM-judge architecture can serve as SafetyNet's output validator for the visual pipeline.
- **Link:** https://arxiv.org/abs/2502.15278

#### [13] CopyrightShield — Diffusion Model Security Against Infringement Attacks
- **arXiv:** 2412.01528 (Dec 2024, updated Aug 2025)
- **Key Insight:** Analyzes how backdoor triggers in training data cause diffusion models to memorize and reproduce copyrighted content. Introduces spatial masking + data attribution to detect poisoned training samples.
- **Direct Relevance:** Understanding the attack vector helps design defenses. SafetyNet needs to assume the underlying diffusion model *may already* memorize protected content.
- **Link:** https://arxiv.org/abs/2412.01528

#### [14] CopyScope — Model-Level Infringement Quantification
- **arXiv:** 2311.12847 (Nov 2023)
- **Key Insight:** Quantifies copyright infringement using FID-based Shapley values across the diffusion pipeline. Identifies which model components are responsible for infringement.
- **Direct Relevance:** Provides a quantitative audit methodology — SafetyNet's logging layer can track infringement risk scores per generation.
- **Link:** https://arxiv.org/pdf/2311.12847

#### [15] Copyright Risks in Text-to-Image Diffusion Models
- **arXiv:** 2311.12803 (Nov 2023)
- **Key Insight:** Comprehensive toolkit demonstrating that diffusion models are highly susceptible to generating copyrighted content even from seemingly unrelated prompts. Includes a benchmark dataset.
- **Direct Relevance:** Establishes the baseline risk that SafetyNet must defend against.
- **Link:** https://arxiv.org/pdf/2311.12803

#### [16] Copyright Infringement Unlearning Dataset & Benchmark
- **arXiv:** 2403.12052 (2024)
- **Key Insight:** Pipeline combining CLIP + ChatGPT + diffusion models to create copyright-violation test sets. Benchmark for evaluating how well a system prevents reproduction of copyrighted content.
- **Direct Relevance:** Use this benchmark to test SafetyNet's Visual Agent safety layer before deployment.
- **Link:** https://arxiv.org/abs/2403.12052

#### [17] PRJ Framework — Cognitively-Inspired Visual Content Safety
- **arXiv:** 2506.03683 (Jun 2025)
- **Key Insight:** Perception–Retrieval–Judgement framework for AI-generated visual safety. Addresses context-dependent harm that binary category filters miss. Handles adversarially induced harm in generated images.
- **Direct Relevance:** Goes beyond simple content filters to semantic-level safety — critical for detecting brand-unsafe or character-unsafe visuals that look "normal" to a keyword scanner.
- **Link:** https://arxiv.org/html/2506.03683

---

## 6. ARXIV PAPERS — MULTI-AGENT GOVERNANCE & CIRCUIT BREAKERS

#### [18] Comprehensive Survey on LLM Full-Stack Safety
- **arXiv:** 2504.15585 (2025)
- **Key Insight:** 900+ reference survey covering data-level, training-level, and deployment-level safety. Section on multi-agent attack vectors is the most comprehensive compilation available.
- **Direct Relevance:** Use as a threat model reference for enumerating all possible failure modes SafetyNet must address.
- **Link:** https://arxiv.org/pdf/2504.15585

#### [19] Monitoring Multi-Agent Systems Against Corruptions via Node Evaluation
- **arXiv:** 2510.19420 (2025)
- **Key Insight:** Proposes per-node evaluation in multi-agent graphs to detect corrupted or misaligned nodes before their outputs propagate. Each node's output is scored against expected behavior before being passed downstream.
- **Direct Relevance:** This is precisely the per-node circuit breaker concept. Apply node evaluation at the output of Script Agent before it feeds the Visual Agents.
- **Link:** https://arxiv.org/pdf/2510.19420

#### [20] G-Safeguard — Topology-Guided Security for Multi-Agent Systems
- **Conference:** ACL 2025
- **Authors:** Wang et al.
- **Key Insight:** Uses the topology of agent communication graphs to identify and neutralize security threats. Shows that network topology (who talks to whom) determines vulnerability surface.
- **Direct Relevance:** LangGraph's directed graph topology defines SafetyNet's threat surface. G-Safeguard's methods apply directly.

#### [21] AEGIS — Online Adaptive AI Content Safety Moderation
- **arXiv:** 2404.05993 (2024)
- **Key Insight:** Ensemble of LLM experts for content safety moderation, adaptable to new harm categories without retraining. Online learning from production data.
- **Direct Relevance:** SafetyNet's moderation layer should be adaptive — new character bible rules or new IP protections should be addable without retraining.
- **Link:** https://arxiv.org/abs/2404.05993

#### [22] NetSafe + AutoDefense — Multi-Agent Defense Systems
- **AutoDefense arXiv:** (Zeng et al., 2024) — Multi-agent LLM defense where a network of specialized agents collectively defend against attacks. Includes a "filter agent" that intercepts and sanitizes inter-agent messages.
- **Direct Relevance:** The "filter agent" concept is SafetyNet's inter-node sanitization layer.

---

## 7. SAFETY BENCHMARKS & EVALUATION DATASETS

Use these to test, red-team, and validate SafetyNet's performance:

| Benchmark | Focus | Key Metric | Link |
|---|---|---|---|
| **R-Judge** (arXiv:2401.10019, EMNLP 2024) | Safety risk awareness across 10 risk categories; 569 agent interaction records | Risk awareness score (GPT-4o best: 74.42%) | https://arxiv.org/abs/2401.10019 |
| **ToolEmu** (Ruan et al., 2024) | LM-emulated sandbox testing diverse tools/scenarios | Tool misuse rate | — |
| **Agent-SafetyBench** (arXiv:2412.14470) | Comprehensive agent safety evaluation (Zhang et al., 2024) | Safety pass rate | https://arxiv.org/abs/2412.14470 |
| **SafeAgentBench** (arXiv:2412.13178) | Embodied LLM agent safety in task planning | Unsafe action rate | — |
| **AgentSafetyBench** (Xiang et al., 2025) | Latest benchmark; covers agentic multi-step safety | — | — |
| **Copyright Infringement Benchmark** (arXiv:2403.12052) | Diffusion model copyright reproduction | CLIP similarity to protected works | https://arxiv.org/abs/2403.12052 |
| **HarmBench** (Mazeika et al., 2024) | Standardized red-teaming with broad harm taxonomies | Attack success rate | — |
| **SORRY-Bench** (arXiv:ICLR 2025) | Safety refusal evaluation | Refusal accuracy | — |
| **InjecAgent** (Zhan et al., 2024) | Indirect prompt injection in tool-integrated agents | Injection success rate | — |

---

## 8. GOVERNANCE STANDARDS & REGULATORY FRAMEWORKS

SafetyNet's deontological layer must be compatible with these external requirements:

### Technical Standards

| Standard | Body | Relevance to SafetyNet |
|---|---|---|
| **NIST AI Risk Management Framework (AI RMF)** + **NIST.AI.600-1** (GenAI Profile, 2024) | NIST | Mandates role-based access, continuous monitoring, adversarial testing, and lifecycle logging — all implemented by SafetyNet's circuit breakers and audit logs |
| **ISO/IEC 42001** (AI Management Systems, 2023) | ISO | Formalizes oversight, logging, and continual improvement for AI systems |
| **ISO/IEC 23894** (AI Risk Management, 2023) | ISO | Risk management methodology directly applicable to pipeline node risk assessment |
| **OWASP Top 10 for LLM Applications v2025** | OWASP | Catalogs exact agent failure classes: prompt injection, tool misuse, memory leakage. SafetyNet must address all 10. |

### Regulatory Frameworks

| Regulation | Jurisdiction | Key Requirements for SafetyNet |
|---|---|---|
| **EU AI Act (2024)** | European Union | Articles 9, 13, 14 require: human intervention capability, traceability logs, conformity assessments. High-risk AI systems (content generation at scale) require mandatory risk management systems. |
| **NSA Cybersecurity Advisories on AI Deployment (2024–2025)** | USA | Identity management for agents, monitoring, data protection — all circuit breaker considerations. |
| **SPIFFE/SPIRE** | Industry standard | Unique workload identities for each agent node — prevents impersonation between agents in the pipeline. |

### IP & Copyright

- **17 U.S.C. § 106** — Exclusive rights of copyright holders. Diffusion models generating substantially similar works = potential infringement liability.
- **EU Copyright Directive (Art. 4 TDM exception)** — Opt-out mechanisms for training data. SafetyNet's IP filter must respect registered opt-outs.
- **Getty Images v. Stability AI (2023, ongoing)** — Key case establishing that commercial diffusion models can be held liable for training on protected images. SafetyNet's visual safety layer is a direct risk mitigation.

---

## 9. SAFETY NET ARCHITECTURE MAPPING

### How the Tools Map to Each Pipeline Node

```
┌─────────────────────────────────────────────────────────────────┐
│                     SAFETY NET LAYER                            │
│                  (Deterministic Rule Engine)                     │
└─────────────────────────────────────────────────────────────────┘
         │                     │                      │
         ▼                     ▼                      ▼
┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
│   SCRIPT AGENT  │   │  IMAGE GEN AGENT │   │  VIDEO GEN AGENT     │
│   (LLM)         │   │  (Diffusion)     │   │  (Diffusion)         │
└────────┬────────┘   └────────┬─────────┘   └──────────┬───────────┘
         │                     │                         │
```

#### Node 1: Script Agent Gate
| SafetyNet Component | Recommended Tool |
|---|---|
| Character Bible Validator | **Guardrails AI** (RAIL schema for script structure) |
| Narrative Constraint Enforcer | **NeMo Guardrails** (Colang rules per scene type) |
| Harmful Content Scanner | **LlamaGuard 4** (I/O classification) |
| Hallucination Detector | **Galileo Agent Control** + Patronus AI |
| Pre-Planning Safety Injection | **TrustAgent** framework (arXiv:2402.01586) |

#### Node 2: Visual Agent Gate
| SafetyNet Component | Recommended Tool |
|---|---|
| IP/Copyright Pre-Filter | **GoG Pipeline** (arXiv:2503.16171) — prompt embedding check |
| Anatomical Safety Validator | **Azure AI Content Safety** (Vision) or **Amazon Rekognition** |
| Brand Safety Classifier | **HiveModeration** (AI-generated content specialist) |
| Post-Generation Audit | **CopyJudge** (arXiv:2502.15278) — LVLM-based output review |
| Prompt Injection Block | **LlamaFirewall** PromptGuard |

#### Circuit Breaker (Orchestrator Level)
| SafetyNet Component | Recommended Tool |
|---|---|
| Workflow Halt Trigger | **Invariant Labs** safety contracts |
| Node Evaluation Score | arXiv:2510.19420 per-node monitoring |
| Trace-Level Audit Log | **Langfuse** (full pipeline tracing) |
| Policy Enforcement | **Galileo Agent Control** (behavioral policies) |
| Access Control Rules | **ProgEnt** (arXiv:2504.11703) least-privilege |

---

## READING PRIORITY ORDER

**Week 1 — Architecture Foundations:**
1. arXiv:2510.13857 — *From Craft to Constitution* (theoretical basis)
2. arXiv:2512.00520 — *Toward a Safe Internet of Agents* (architecture)
3. arXiv:2402.01586 — *TrustAgent* (Agent Constitution pattern)
4. arXiv:2505.03574 — *LlamaFirewall* (open-source implementation)

**Week 2 — Copyright & Visual Safety:**
5. arXiv:2503.16171 — *Guardians of Generation* (copyright shielding pipeline)
6. arXiv:2502.15278 — *CopyJudge* (automated infringement detection)
7. arXiv:2412.01528 — *CopyrightShield* (diffusion model backdoors)

**Week 3 — Multi-Agent Governance:**
8. arXiv:2509.23994 — *Policy-as-Prompt* (policy-to-practice gap)
9. arXiv:2504.11703 — *ProgEnt* (privilege control)
10. arXiv:2510.19420 — *Node Evaluation for Multi-Agent Monitoring*

**Ongoing — Evaluation:**
11. arXiv:2401.10019 — *R-Judge* (safety benchmark)
12. arXiv:2412.14470 — *Agent-SafetyBench*

---

*Document compiled June 2026. All arXiv links are permanent. GitHub repos may update; check for latest releases.*
