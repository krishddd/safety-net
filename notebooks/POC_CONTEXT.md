# Guardrails PoC — context for a new session

Paste this into a fresh session to pick up where we left off.

## What this is
A **simple, self-contained** proof-of-concept notebook: [`notebooks/guardrails_poc.ipynb`](guardrails_poc.ipynb).
It shows guardrail techniques in front of a **text-to-image agent** — no dependency on the
SafetyNet package, just plain functions so the methods are easy to read.

## What the notebook does (9 steps)
1. install packages, 2. imports, 3. `clean_text()` (fold away invisible/look-alike characters),
4. `check_input()` (prompt-injection + banned-content + PII checks), 5. load **SD-Turbo**
text-to-image model, 6. `guarded_generate()` (guard runs before the model),
7. safe prompt → image, 8. bad prompt → blocked, 9. optional NSFW check on the generated image.

## How to run
- Best in **Google Colab with a GPU** (Runtime → Change runtime type → GPU). First run downloads
  the SD-Turbo + NSFW models.
- Locally: needs `diffusers transformers accelerate torch` and ideally a CUDA GPU (CPU works but is slow).

## Deliberately kept out (so it stays simple)
- No semantic/model-based injection detection (the keyword checks miss paraphrases — see the real
  benchmark below).
- No gateway/proxy, no audit log, no ethics engine — those live in the full SafetyNet repo.

## Where to take it next
- Swap the keyword `check_input()` for a model (PromptGuard) — keyword matching only catches ~16%
  of real injections (measured on deepset/prompt-injections; see `docs/BENCHMARKS.md`).
- Add more attack examples (homoglyph/leetspeak/base64) and show `clean_text()` defeating them.
- Add output-text moderation, and wire the notebook's agent behind the SafetyNet gateway
  (`UPSTREAM_TYPE`, `docs/INTEGRATIONS.md`) once we move from PoC to the real pipeline.
- Replace SD-Turbo with the team's chosen image agent (e.g. a Dify image app).

## Suggested opening message for the new session
> "Continue the guardrails PoC in `notebooks/guardrails_poc.ipynb`. Next: <pick one of the
> 'next' items above>. Keep it simple and notebook-level."
