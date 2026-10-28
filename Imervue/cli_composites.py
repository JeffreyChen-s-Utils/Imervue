"""Collage and stereo-pair CLI commands with their distinct failure policies."""
from __future__ import annotations

import sys
from PIL import Image
from pathlib import Path
from Imervue.cli_native import _rgb
from Imervue.cli_paths import _NO_INPUTS, _checked_path, _ensure_parent, iter_image_paths
from Imervue.image.output_policy import OutputPolicy, write_output
from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.image.shown import load_shown_rgba


def cmd_collage(args) -> int:
    """Composite many inputs into one grid montage."""
    paths = iter_image_paths(args.inputs, recursive=args.recursive)
    if not paths:
        print(_NO_INPUTS, file=sys.stderr)
        return 1
    try:
        out = _checked_path(args.out)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    from Imervue.image.collage import build_collage
    images, errors = [], 0
    for path in paths:
        try:
            images.append(load_shown_rgba(path))
        except IMAGE_READ_ERRORS as exc:   # one unreadable file must not end the run
            print(f"error: {path}: {exc}", file=sys.stderr)
            errors += 1
    if not images:
        return 1
    _ensure_parent(out)
    collage = build_collage(images, args.columns, cell=(args.cell_width, args.cell_height),
                            gap=args.gap, margin=args.margin, background=_rgb(args.background))
    write_output("", out, lambda stage: Image.fromarray(collage, mode="RGBA").save(stage),
                 OutputPolicy("replace"))
    print(f"{len(images)} images -> {out}")
    return 1 if errors else 0


def cmd_anaglyph(args) -> int:
    """Combine a left/right stereo pair into one red-cyan anaglyph."""
    left, right = Path(args.left), Path(args.right)
    if not left.is_file() or not right.is_file():
        print("both left and right must be existing image files", file=sys.stderr)
        return 1
    try:
        out = _checked_path(args.out) if args.out else left.with_name(
            f"{left.stem}_anaglyph.png")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    from Imervue.image.anaglyph import anaglyph
    try:
        pair = load_shown_rgba(left), load_shown_rgba(right)
    except IMAGE_READ_ERRORS as exc:   # reported like every other subcommand, no traceback
        print(f"error: {exc}", file=sys.stderr)
        return 1
    result = anaglyph(*pair, args.method)
    _ensure_parent(out)
    write_output("", out, lambda stage: Image.fromarray(result, mode="RGBA").save(stage),
                 OutputPolicy("replace"))
    print(f"{left} + {right} -> {out}")
    return 0
