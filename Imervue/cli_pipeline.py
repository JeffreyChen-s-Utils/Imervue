"""Pipeline file validation and ordered image execution."""
from __future__ import annotations

import json
import sys
from PIL import Image
from pathlib import Path
from Imervue.cli_batch import _write
from Imervue.cli_paths import _NO_INPUTS, iter_image_paths
from Imervue.cli_pipeline_steps import _PIPELINE_OPS
from Imervue.image.shown import load_shown_rgba


_MAX_PIPELINE_STEPS = 50


def load_pipeline(file: str) -> list[dict]:
    """Read a pipeline JSON file (a list of steps, or ``{"pipeline": [...]}``)."""
    raw = json.loads(Path(file).read_text(encoding="utf-8-sig"))   # a BOM from an editor is fine
    steps = raw["pipeline"] if isinstance(raw, dict) and "pipeline" in raw else raw
    if not isinstance(steps, list):
        raise ValueError('pipeline must be a list, or {"pipeline": [...]}')
    return steps


def validate_pipeline(steps: list) -> list[str]:
    """Return a list of human-readable validation errors (empty when valid)."""
    errors: list[str] = []
    if len(steps) > _MAX_PIPELINE_STEPS:
        errors.append(f"too many steps ({len(steps)} > {_MAX_PIPELINE_STEPS})")
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("op"), str):
            errors.append(f"step {i}: each step must be an object with an 'op' name")
        elif step["op"] not in _PIPELINE_OPS:
            errors.append(f"step {i}: unknown op {step['op']!r}; "
                          f"known: {sorted(_PIPELINE_OPS)}")
    return errors


def op_pipeline(src: Path, target: Path, args) -> None:
    arr = load_shown_rgba(src)
    for index, step in enumerate(args.pipeline_steps):
        try:
            arr = _PIPELINE_OPS[step["op"]](arr, step)
        except TypeError as exc:   # a parameter of the wrong type, e.g. null: this image's error
            raise ValueError(f"pipeline step {index} ({step['op']}): {exc}") from exc
    Image.fromarray(arr, mode="RGBA").save(target)


def cmd_pipeline(args) -> int:
    """Apply an ordered JSON pipeline of operations to each input image."""
    try:
        steps = load_pipeline(args.file)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = validate_pipeline(steps)
    if errors:
        for err in errors:
            print(f"pipeline error: {err}", file=sys.stderr)
        return 2
    paths = iter_image_paths(args.inputs, recursive=args.recursive)
    if not paths:
        print(_NO_INPUTS, file=sys.stderr)
        return 1
    args.pipeline_steps = steps
    return _write(args, paths, op_pipeline, "_pipeline", lambda _a: ".png")
