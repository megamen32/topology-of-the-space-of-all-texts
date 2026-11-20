#!/usr/bin/env python3
"""Reproduce two Eval Harness v2 controls and extend their own streams to one page."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from tempfile import TemporaryDirectory

if __package__:
    from . import eval_harness_v2 as harness
else:
    import eval_harness_v2 as harness


PAGE_CHARS = 4096
HISTORICAL_BUDGET = 512
CONFIGS = (
    {"model": "paragraph", "temp": 0.85, "branch": 64},
    {"model": "word", "temp": 0.55},
)
LIMITS = {
    "paragraph": ("max_paragraphs", harness.PARAGRAPH_MAX_PARAGRAPHS),
    "word": ("max_tokens", harness.WORD_MAX_TOKENS),
}
LEADERBOARD = "models/eval_harness_v2/leaderboard.json"
JUDGE = "models/eval_harness_v2/llm_judge_qwen3_4b_v3.json"


def measure(text: str) -> dict:
    data = text.encode("utf-8")
    return {"chars": len(text), "utf8_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def require_prefix(prefix: str, stream: str, model: str, seed: int) -> None:
    if not stream.startswith(prefix):
        raise AssertionError(f"{model}, seed {seed}: output diverged inside its {len(prefix)}-character prefix")


def write_sample(root: Path, cfg: dict, seed: int) -> dict:
    model = cfg["model"]
    limit_name, limit = LIMITS[model]
    budget = PAGE_CHARS
    native = harness.generate(cfg, seed, budget)
    historical = harness.generate(cfg, seed, HISTORICAL_BUDGET)
    require_prefix(historical, native, model, seed)

    stream = native
    attempts = [{"length": budget, limit_name: limit, **measure(stream)}]
    # The paragraph loop measures its final join. Only the paragraph cap can
    # leave it short. The word loop measures a spaced join before detok().
    raise_limit = model == "paragraph"
    while len(stream) < PAGE_CHARS:
        if model == "word":
            budget += PAGE_CHARS - len(stream)
        if raise_limit:
            limit *= 2
        longer = harness.generate(cfg, seed, budget, **{limit_name: limit})
        require_prefix(stream, longer, model, seed)
        attempts.append({"length": budget, limit_name: limit, **measure(longer)})
        raise_limit = model == "paragraph" or len(longer) == len(stream)
        stream = longer

    page = stream[:PAGE_CHARS]
    require_prefix(native, page, model, seed)
    folder = Path(model) / str(seed)
    (root / folder).mkdir(parents=True)
    row = {
        "model": model,
        "config": cfg,
        "seed": seed,
        "assembly": "native" if len(native) == PAGE_CHARS else "same_seed_continuation",
        "native_range": [0, len(native)],
        "continuation_range": [len(native), len(page)],
        "trimmed_chars": len(stream) - len(page),
        "attempts": attempts,
    }
    for key, text in (("native_512", historical), ("native_4096", native), ("page", page)):
        path = folder / (key + ".txt")
        (root / path).write_bytes(text.encode("utf-8"))
        row[key] = {"path": path.as_posix(), **measure(text)}
    return row


def provenance() -> dict:
    archived = json.loads((harness.ROOT / LEADERBOARD).read_bytes())["leaderboard"]
    archived_configs = [row["cfg"] for row in archived]
    for cfg in CONFIGS:
        if cfg not in harness.configs or cfg not in archived_configs:
            raise ValueError(f"Configuration absent from the historical grid or leaderboard: {cfg}")

    sources = {
        "experiments/student_comparison_pages.py": Path(__file__),
        "experiments/eval_harness_v2.py": Path(harness.__file__),
        **{name: harness.ROOT / name for name in (
            LEADERBOARD, JUDGE, "models/word_student_v1/word_student_v1.json",
            "models/paragraph_student_v1/paragraph_student_v1.json",
        )},
    }
    return {
        "runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                    "regex": harness.re.__version__},
        "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sources.items()},
        "config_origin": {
            "word": f"{LEADERBOARD}, lowest final_score",
            "paragraph": f"{JUDGE}, best wins minus losses among direct judge votes",
        },
        "historical_budget": HISTORICAL_BUDGET,
        "page_chars": PAGE_CHARS,
        "range_unit": "zero-based half-open offsets in Unicode code points",
        "output": "Historical detokenization and native character slice, then stream[:4096], then UTF-8 verbatim.",
    }


def seed_range(value: str) -> range:
    try:
        first, sep, last = value.partition("-")
        start = int(first)
        stop = int(last) if sep else start
        if 0 <= start <= stop:
            return range(start, stop + 1)
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected a nonnegative seed or an inclusive range such as 10-15")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True, type=seed_range, help="one seed or an inclusive range")
    parser.add_argument("--out", required=True, type=Path, help="new directory for this batch")
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output directory already exists: {args.out}")
    manifest = provenance()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{args.out.name}-", dir=args.out.parent) as tmp:
        batch = Path(tmp) / "batch"
        batch.mkdir()
        manifest["samples"] = [write_sample(batch, cfg, seed) for seed in args.seeds for cfg in CONFIGS]
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        (batch / "manifest.json").write_bytes(encoded)
        batch.rename(args.out)
    print(f"{len(manifest['samples'])} pages, manifest SHA-256 {hashlib.sha256(encoded).hexdigest()}")


if __name__ == "__main__":
    main()
