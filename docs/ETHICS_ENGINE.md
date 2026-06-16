# The Ethics Engine

This is the mechanism SafetyNet is named for. It is specified here precisely so the
implementation cannot improvise it.

## Score convention

`score ∈ [0, 1]` is a **safety** score: `1.0` = fully safe, `0.0` = maximally unsafe. *Every*
framework and *every* scanner uses this same direction, so signs can never get flipped between
modules. The consequentialism framework converts its net-harm estimate via `safety = 1 - net_harm`.

## Decision is a pure function of score — one source of truth

There is exactly one mapping, the `band(score)` helper in `core/types.py`, and every verdict's
`Decision` is derived from its `score` through it:

| score range      | Decision |
|------------------|----------|
| `[0.00, 0.33)`   | `BLOCK`  |
| `[0.33, 0.66)`   | `FLAG`   |
| `[0.66, 1.00]`   | `ALLOW`  |

No framework gets a *second, independent* decision boundary. In particular, consequentialism's
`harm_threshold` is an **internal harm-model knob** (it shapes how raw harm signals translate to
net harm) — it never decides `BLOCK`/`FLAG`/`ALLOW` by itself. A framework with only categorical
intuition still emits a `score` (its band midpoint: `BLOCK→0.16`, `FLAG→0.50`, `ALLOW→0.83`), and
`band()` round-trips it to the same `Decision`. Because the aggregator and the per-framework
verdicts share the identical `band()`, a `0.4` is **always** `FLAG`, everywhere.

## Stances (how verdicts combine)

- **`deontology_veto`** (default): if any *deontic* framework returns `BLOCK`, the aggregate is
  `BLOCK` and the consequentialist scores are discarded — this *arrests consequentialism*. The
  aggregate keeps `deontic=True` so the circuit breaker can halt unconditionally. Otherwise it
  falls through to `weighted`.
- **`weighted`**: aggregate safety = weighted mean of per-framework scores (weights normalized to
  sum `1.0` at policy load); `Decision = band(mean)`. Every framework already carries a numeric
  score, so the score *is* the contribution — nothing extra to "modulate".
- **`strictest`**: the most severe verdict wins. Because a lower score maps to a more severe band,
  the most-severe verdict is exactly the minimum-score verdict — so this is simultaneously
  "most severe", "min score", and band-consistent.

## `FLAG` is operationalized (not just a label)

A `FLAG` does **not** block on its own. It:
1. is recorded in the audit log with its rationale,
2. feeds the circuit breaker's cumulative risk (a FLAG adds `1 - score`), and
3. optionally routes the node to a human-review queue when `human_review_on_flag: true`.

Default behavior is **log-and-continue while accruing risk**.

## Worked example (this is `tests/test_ethics.py`'s anchor)

> Action = *"render a scene where the hero lies to a child to spare their feelings."*

- **Deontology** has an inviolable duty `no_deception_of_minors`. It fires → `BLOCK`,
  `score = 0.10`, `deontic = True`, rationale `"violates duty: no_deception_of_minors"`.
- **Consequentialism** estimates net benefit (the child is comforted) → `ALLOW`, `score = 0.80`.

| stance            | computation                         | result            |
|-------------------|-------------------------------------|-------------------|
| `deontology_veto` | deontic BLOCK present → veto        | **BLOCK** (0.10)  |
| `weighted` (0.5/0.5) | mean(0.10, 0.80) = 0.45 → `band`   | **FLAG** (0.45)   |

The same inputs produce different outcomes under different stances, proving the stance — not an
accident of implementation — drives the decision, and that a good outcome score can never override
a duty under the default stance.

## Interaction with the circuit breaker

A hard `BLOCK` short-circuits the breaker **immediately and unconditionally** (it halts even at
zero accumulated risk). Only `FLAG`s and sub-threshold scores feed the cumulative risk → threshold
logic. Without this, several "clean" nodes could outvote one bad node and let it through — exactly
the ends-justify-means tradeoff `deontology_veto` exists to arrest. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) and `core/circuit_breaker.py`.

## Extending

Add a framework by implementing the `EthicalFramework` protocol (`name`, `is_deontic`,
`evaluate(action, context) -> Verdict`) and registering it in `guard.build_ethics_engine`.
Virtue Ethics and Care Ethics are natural next additions; a fully declarative policy DSL (each
framework expressed as data) is the longer-term direction (cf. *Policy-as-Prompt*, arXiv:2509.23994).
