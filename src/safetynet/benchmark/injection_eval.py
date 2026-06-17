"""Evaluate a prompt-injection backend against a REAL labeled dataset.

Unlike the bundled samples (which are tuned to pass), this runs any injection backend over a
third-party dataset and reports honest precision/recall/F1. It exists specifically to measure how
far the dependency-free ``pattern`` backend falls short on real, paraphrased injections — and to
let you compare it head-to-head against the model-backed ``promptguard`` backend with one command.

    # offline default (deepset/prompt-injections, ~662 labeled prompts; needs network + pyarrow)
    python -m safetynet.benchmark.injection_eval --dataset deepset --backend pattern

    # model backend (needs the [guard] extra + the PromptGuard weights)
    python -m safetynet.benchmark.injection_eval --dataset deepset --backend promptguard

    # your own data
    python -m safetynet.benchmark.injection_eval --dataset mydata.jsonl --backend pattern
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..core.types import Action, Context
from ..scanners.prompt_injection import PromptInjectionScanner
from .metrics import ConfusionMatrix, confusion

logger = logging.getLogger("safetynet.benchmark.injection_eval")

HF_DATASET = "deepset/prompt-injections"
DEFAULT_CACHE = Path("benchmark_cache")
_UNSAFE_TOKENS = {"1", "true", "injection", "unsafe", "malicious", "jailbreak", "yes"}


@dataclass
class EvalRow:
    text: str
    expected_unsafe: bool
    predicted_unsafe: bool
    decision: str


def _is_unsafe(value, unsafe_value=1) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == int(unsafe_value)
    return str(value).strip().lower() in _UNSAFE_TOKENS


def _read_parquet(raw: bytes, text_col: str | None, label_col: str | None) -> list[tuple[str, bool]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Reading parquet datasets needs pyarrow: pip install '.[eval]'") from exc
    table = pq.read_table(io.BytesIO(raw))
    cols = table.column_names
    tc = text_col or ("text" if "text" in cols else cols[0])
    lc = label_col or ("label" if "label" in cols else cols[-1])
    d = table.to_pydict()
    return [(str(t), _is_unsafe(v)) for t, v in zip(d[tc], d[lc], strict=False)]


def load_deepset(cache_dir: Path = DEFAULT_CACHE, timeout: float = 30.0) -> list[tuple[str, bool]]:
    """Download (and cache) the deepset/prompt-injections dataset; return (text, is_injection)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    api = f"https://huggingface.co/api/datasets/{HF_DATASET}/tree/main/data"
    files = [f["path"] for f in json.load(urllib.request.urlopen(api, timeout=timeout)) if f.get("path", "").endswith(".parquet")]
    rows: list[tuple[str, bool]] = []
    for path in files:
        local = cache_dir / path.replace("/", "_")
        if local.exists():
            raw = local.read_bytes()
        else:
            url = f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main/{path}"
            raw = urllib.request.urlopen(url, timeout=timeout).read()
            local.write_bytes(raw)
        rows += _read_parquet(raw, None, None)
    return rows


def load_file(path: str, text_col: str | None = None, label_col: str | None = None) -> list[tuple[str, bool]]:
    p = Path(path)
    if p.suffix == ".parquet":
        return _read_parquet(p.read_bytes(), text_col, label_col)
    if p.suffix in (".jsonl", ".json"):
        out = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rec = json.loads(line)
                out.append((str(rec.get(text_col or "text")), _is_unsafe(rec.get(label_col or "expected_unsafe"))))
        return out
    if p.suffix == ".csv":
        import csv

        with p.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            tc = text_col or ("text" if "text" in reader.fieldnames else reader.fieldnames[0])
            lc = label_col or ("label" if "label" in reader.fieldnames else reader.fieldnames[-1])
            return [(row[tc], _is_unsafe(row[lc])) for row in reader]
    raise ValueError(f"unsupported dataset file type: {p.suffix}")


def evaluate_scanner(
    prompts: list[tuple[str, bool]], scanner, *, flag_is_unsafe: bool = True
) -> tuple[ConfusionMatrix, list[EvalRow]]:
    """Run a scanner over (text, expected_unsafe) pairs and return (confusion, per-row results)."""
    ctx = Context()
    rows: list[EvalRow] = []
    for text, expected in prompts:
        decision = scanner.scan(Action("eval", "generate_text", text), ctx).decision.value
        predicted = decision == "BLOCK" or (flag_is_unsafe and decision == "FLAG")
        rows.append(EvalRow(text, expected, predicted, decision))
    cm = confusion([(r.predicted_unsafe, r.expected_unsafe) for r in rows])
    return cm, rows


def _build_scanner(backend: str, model_id: str | None) -> PromptInjectionScanner:
    if backend == "promptguard":
        return PromptInjectionScanner(backend="promptguard", model_id=model_id)
    return PromptInjectionScanner(backend="pattern")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="safetynet.benchmark.injection_eval")
    parser.add_argument("--dataset", default="deepset", help="'deepset' or a path to .parquet/.jsonl/.csv")
    parser.add_argument("--backend", choices=["pattern", "promptguard"], default="pattern")
    parser.add_argument("--model-id", default=None, help="model id for the promptguard backend")
    parser.add_argument("--limit", type=int, default=0, help="evaluate only the first N rows (0 = all)")
    parser.add_argument("--show-misses", type=int, default=5, help="print N false negatives (missed injections)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    prompts = load_deepset() if args.dataset == "deepset" else load_file(args.dataset)
    if args.limit:
        prompts = prompts[: args.limit]

    scanner = _build_scanner(args.backend, args.model_id)
    cm, rows = evaluate_scanner(prompts, scanner)

    print(f"dataset={args.dataset}  backend={args.backend}  n={cm.total}")
    print(f"accuracy {cm.accuracy:.3f} | precision {cm.precision:.3f} | recall {cm.recall:.3f} | f1 {cm.f1:.3f}")
    print(f"confusion: TP={cm.tp} FP={cm.fp} TN={cm.tn} FN={cm.fn}")
    misses = [r for r in rows if r.expected_unsafe and not r.predicted_unsafe]
    if misses and args.show_misses:
        print(f"\nmissed injections ({len(misses)} total), first {args.show_misses}:")
        for r in misses[: args.show_misses]:
            print(f"  - {r.text[:90]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
