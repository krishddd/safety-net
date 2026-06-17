# Benchmark Harness

The harness measures how well SafetyNet's gate (ethics engine + scanners) detects unsafe
content on labeled scenarios. It is the evaluation hook called for in the research reference
(R-Judge arXiv:2401.10019, Agent-SafetyBench arXiv:2412.14470).

## Honest baseline on REAL data (read this first)

The bundled samples below are tuned and report ~100% — that number is **not** evidence of real
performance. For an honest measurement, `safetynet.benchmark.injection_eval` runs an injection
backend over the third-party **deepset/prompt-injections** dataset (662 labeled prompts, incl.
paraphrased / multilingual / role-play injections).

Result for the dependency-free **`pattern`** backend (the default), reproduced with
`python -m safetynet.benchmark.injection_eval --dataset deepset --backend pattern`:

| backend | n | accuracy | precision | recall | F1 | confusion |
|---|---|---|---|---|---|---|
| `pattern` (keywords) | 662 | 0.665 | **1.000** | **0.156** | 0.270 | TP41 FP0 TN399 FN222 |

**Takeaway:** the keyword heuristic is high-precision but **catches only ~16% of real
injections** — it reliably flags "ignore previous instructions" but misses paraphrases
("forget about all the previous orders"), role-play, and non-English attacks. **Do not ship the
default scanners alone.** Enable the model backend and re-run the same command to compare:

```bash
pip install '.[guard]'          # transformers + torch + the PromptGuard weights
python -m safetynet.benchmark.injection_eval --dataset deepset --backend promptguard
```

(`--dataset` also accepts a local `.parquet`/`.jsonl`/`.csv`; needs the `[eval]` extra for parquet.)

## What it measures

Each scenario carries a boolean `expected_unsafe` label. SafetyNet evaluates the text through a
single PRE-stage gate and produces a `Decision` (`ALLOW`/`FLAG`/`BLOCK`). The harness maps that
to a binary prediction and scores it:

- **Detection mode** (default): `FLAG` or `BLOCK` counts as "predicted unsafe" — *did the guard
  notice?*
- **Refusal mode** (`--block-only`): only `BLOCK` counts — *did the guard refuse?*

Reported metrics: accuracy, precision, recall, F1, and the confusion matrix where a false
**negative** (missed harm) is the costly error and a false **positive** is over-blocking.

## Running

```bash
# Bundled offline sample (12 labeled scenarios across benign/ip/injection/violence/deception/harm)
python examples/run_benchmark.py
python -m safetynet.benchmark                       # same, via the CLI

# A real dataset
python -m safetynet.benchmark --dataset path/to/r-judge.jsonl       --format rjudge
python -m safetynet.benchmark --dataset path/to/agentsafetybench.jsonl --format agentsafetybench
python -m safetynet.benchmark --dataset mydata.jsonl --format jsonl  # generic schema
python -m safetynet.benchmark --block-only                          # refusal mode
python -m safetynet.benchmark --policy policies/strict.yaml         # evaluate a different policy
```

## Dataset formats

- **Generic JSONL** — one object per line: `{"id", "text", "expected_unsafe", "category"}`.
- **R-Judge** (`load_rjudge`) — tolerant loader looking for `contents`/`conversation`/`scenario`
  text and a `label`/`risk` flag (or inverted `is_safe`/`safe`).
- **Agent-SafetyBench** (`load_agentsafetybench`) — looks for `instruction`/`prompt`/`query` text
  and a `label`/`unsafe`/`safe` flag.

Schemas vary by dataset release, so the adapters are deliberately tolerant; verify the mapping
on a few rows before trusting aggregate numbers. The real datasets require download — only the
small sample is bundled so the harness and its tests run offline.

## Interpreting results on the sample

The default policy is tuned to the sample's categories, so detection-mode accuracy is ~1.0;
this is a **regression baseline for the stubs**, not a claim about real-world performance. The
interesting signal is refusal mode: the gore/violence scene `FLAG`s (accrues risk) rather than
`BLOCK`ing, illustrating the FLAG-vs-BLOCK distinction. Swap in a real moderation backend
(`[guard]` or `[anthropic]`) and re-run against a real dataset to get meaningful numbers.

## Extending

`run_benchmark(scenarios, policy, flag_counts_as_unsafe=...)` returns a `BenchmarkReport` with
`.confusion`, `.by_key("category")`, `.misclassified()`, and `.summary()`. Add a loader for a new
dataset by emitting `Scenario` objects; everything downstream is format-agnostic.
