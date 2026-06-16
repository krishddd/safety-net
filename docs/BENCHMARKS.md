# Benchmark Harness

The harness measures how well SafetyNet's gate (ethics engine + scanners) detects unsafe
content on labeled scenarios. It is the evaluation hook called for in the research reference
(R-Judge arXiv:2401.10019, Agent-SafetyBench arXiv:2412.14470).

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
