"""Read-only image reporters and ordered CLI report formatting."""
from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from Imervue.image.dimensions import probe_image
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.shown import load_shown_rgba


_BYTES_PER_KB = 1024.0


def op_info(src: Path, _args) -> dict:
    fmt, mode, width, height = probe_image(src)   # the upright size; libraw's for a RAW
    return {
        "path": str(src), "format": fmt, "mode": mode, "width": width, "height": height,
        "size_kb": round(src.stat().st_size / _BYTES_PER_KB, 1),
    }


def op_stats(src: Path, _args) -> dict:
    from Imervue.image.quality_metrics import quality_metrics
    metrics = quality_metrics(load_shown_rgba(src))
    return {"path": str(src), **{k: round(v, 3) for k, v in metrics.items()}}


_REPORTERS = {"info": op_info, "stats": op_stats}


def _report(args, paths: Sequence[Path], operation) -> int:
    results = []
    errors = 0
    for path in paths:
        try:
            results.append(operation(path, args))
        except IMAGE_READ_ERRORS as exc:   # one unreadable file must not end the run
            print(f"error: {path}: {exc}", file=sys.stderr)
            errors += 1
    if getattr(args, "json", False):
        print(json.dumps(results, indent=2))
    else:
        for item in results:
            print("  ".join(f"{k}={v}" for k, v in item.items()))
    return 1 if errors else 0
