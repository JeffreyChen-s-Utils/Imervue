"""Headless batch command-line interface.

Runs the app's pure image operations from the shell without starting the Qt
GUI, e.g.::

    py -m Imervue.cli resize photos/ --max 1600 --out web/
    py -m Imervue.cli watermark a.jpg --text "© Me" --corner bottom-right
    py -m Imervue.cli info *.png --json

Only pure NumPy / Pillow code is imported here — never ``Imervue.gui`` or any
Qt/OpenGL module — so the CLI stays usable on a headless server. Input
collection, output-path resolution and each operation are small testable units;
``main`` only wires argparse to them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
from PIL import Image

_IMAGE_EXTS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif",
    ".heic", ".heif", ".avif", ".jxl",
})
_FORMAT_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
_BYTES_PER_KB = 1024.0
_CLI_VERSION = "1.0"
_NO_INPUTS = "no input images found"
_EMIT_JSON = "emit JSON"


def iter_image_paths(inputs: Iterable[str], *, recursive: bool) -> list[Path]:
    """Expand *inputs* (files or directories) into a sorted list of image paths."""
    found: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            walker = path.rglob("*") if recursive else path.glob("*")
            found.extend(p for p in walker
                         if p.is_file() and p.suffix.lower() in _IMAGE_EXTS)
        elif path.is_file():
            found.append(path)
    return sorted(set(found))


def output_path(src: Path, out_dir: str | None, suffix: str, ext: str | None) -> Path:
    """Resolve the destination path for *src* given --out / suffix / new extension."""
    new_ext = ext if ext is not None else src.suffix
    if out_dir:
        return Path(out_dir) / f"{src.stem}{new_ext}"
    return src.with_name(f"{src.stem}{suffix}{new_ext}")


def _load_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.array(img.convert("RGBA"))


# --- operations -------------------------------------------------------------

def _resize_to(img: Image.Image, max_edge: int) -> Image.Image:
    resized = img.copy()
    resized.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return resized


def op_convert(src: Path, target: Path, args) -> None:
    fmt = args.format.upper()
    with Image.open(src) as img:
        rgb = img.convert("RGB") if fmt == "JPEG" else img.convert("RGBA")
        rgb.save(target, format=fmt, quality=args.quality)


def op_resize(src: Path, target: Path, args) -> None:
    with Image.open(src) as img:
        _resize_to(img, args.max).save(target)


def op_thumbnail(src: Path, target: Path, args) -> None:
    with Image.open(src) as img:
        _resize_to(img.convert("RGBA"), args.size).save(target)


def op_watermark(src: Path, target: Path, args) -> None:
    from Imervue.image.watermark import WatermarkOptions, apply_watermark
    with Image.open(src) as img:
        apply_watermark(img.convert("RGBA"), WatermarkOptions(
            text=args.text, corner=args.corner, opacity=args.opacity)).save(target)


def op_optimize(src: Path, target: Path, args) -> None:
    from Imervue.image.optimize import encode_to_budget
    data, _quality = encode_to_budget(_load_rgba(src), args.max_kb, args.format.upper())
    target.write_bytes(data)


def op_dehaze(src: Path, target: Path, args) -> None:
    from Imervue.image.dehaze import dehaze
    Image.fromarray(dehaze(_load_rgba(src), args.strength), mode="RGBA").save(target)


def op_clahe(src: Path, target: Path, args) -> None:
    from Imervue.image.clahe import apply_clahe
    Image.fromarray(apply_clahe(_load_rgba(src), args.clip, args.tiles), mode="RGBA").save(target)


def op_dither(src: Path, target: Path, args) -> None:
    from Imervue.image.dither import ordered_dither
    Image.fromarray(ordered_dither(_load_rgba(src), args.levels), mode="RGBA").save(target)


def op_distort(src: Path, target: Path, args) -> None:
    from Imervue.image.distort import distort
    Image.fromarray(distort(_load_rgba(src), args.mode, args.strength), mode="RGBA").save(target)


def op_autoorient(src: Path, target: Path, _args) -> None:
    from Imervue.image.orientation import oriented_array
    Image.fromarray(oriented_array(str(src)), mode="RGBA").save(target)


def op_strip(src: Path, target: Path, _args) -> None:
    # Re-save without forwarding exif/icc/xmp — Pillow omits metadata by default.
    with Image.open(src) as img:
        img.save(target)


# --- pipeline (chain several operations from a JSON file) -------------------

_MAX_PIPELINE_STEPS = 50
_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def _step_dehaze(arr, p):
    from Imervue.image.dehaze import dehaze
    return dehaze(arr, float(p.get("strength", 1.0)))


def _step_clahe(arr, p):
    from Imervue.image.clahe import apply_clahe
    return apply_clahe(arr, float(p.get("clip", 2.0)), int(p.get("tiles", 8)))


def _step_dither(arr, p):
    from Imervue.image.dither import ordered_dither
    return ordered_dither(arr, int(p.get("levels", 2)))


def _step_distort(arr, p):
    from Imervue.image.distort import distort
    return distort(arr, str(p.get("mode", "swirl")), float(p.get("strength", 0.5)))


def _step_clarity(arr, p):
    from Imervue.image.local_contrast import apply_clarity
    return apply_clarity(arr, float(p.get("amount", 0.5)))


def _step_texture(arr, p):
    from Imervue.image.local_contrast import apply_texture
    return apply_texture(arr, float(p.get("amount", 0.5)))


def _step_grayscale(arr, _p):
    luma = np.clip(np.rint(arr[..., :3].astype(np.float32) @ _LUMA), 0, 255).astype(np.uint8)
    out = arr.copy()
    out[..., :3] = luma[..., None]
    return out


def _step_invert(arr, _p):
    out = arr.copy()
    out[..., :3] = 255 - out[..., :3]
    return out


def _step_watermark(arr, p):
    from Imervue.image.watermark import WatermarkOptions, apply_watermark
    marked = apply_watermark(Image.fromarray(arr, "RGBA"), WatermarkOptions(
        text=str(p.get("text", "")), corner=str(p.get("corner", "bottom-right")),
        opacity=float(p.get("opacity", 0.6))))
    return np.array(marked)


_PIPELINE_OPS = {
    "dehaze": _step_dehaze, "clahe": _step_clahe, "dither": _step_dither,
    "distort": _step_distort, "clarity": _step_clarity, "texture": _step_texture,
    "grayscale": _step_grayscale, "invert": _step_invert, "watermark": _step_watermark,
}


def load_pipeline(file: str) -> list[dict]:
    """Read a pipeline JSON file (a list of steps, or ``{"pipeline": [...]}``)."""
    raw = json.loads(Path(file).read_text(encoding="utf-8"))
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
        if not isinstance(step, dict) or "op" not in step:
            errors.append(f"step {i}: each step must be an object with an 'op'")
        elif step["op"] not in _PIPELINE_OPS:
            errors.append(f"step {i}: unknown op {step['op']!r}; "
                          f"known: {sorted(_PIPELINE_OPS)}")
    return errors


def op_pipeline(src: Path, target: Path, args) -> None:
    arr = _load_rgba(src)
    for step in args.pipeline_steps:
        arr = _PIPELINE_OPS[step["op"]](arr, step)
    Image.fromarray(arr, mode="RGBA").save(target)


def op_info(src: Path, _args) -> dict:
    with Image.open(src) as img:
        width, height = img.size
        info = {
            "path": str(src), "format": img.format, "mode": img.mode,
            "width": width, "height": height,
        }
    info["size_kb"] = round(src.stat().st_size / _BYTES_PER_KB, 1)
    return info


def op_stats(src: Path, _args) -> dict:
    from Imervue.image.quality_metrics import quality_metrics
    metrics = quality_metrics(_load_rgba(src))
    return {"path": str(src), **{k: round(v, 3) for k, v in metrics.items()}}


_REPORTERS = {"info": op_info, "stats": op_stats}
# command → (operation, output-suffix, extension resolver)
_WRITE_SPEC = {
    "convert": (op_convert, "_converted", lambda a: _FORMAT_EXT.get(a.format.upper(), ".png")),
    "resize": (op_resize, "_resized", lambda _a: None),
    "thumbnail": (op_thumbnail, "_thumb", lambda _a: ".png"),
    "watermark": (op_watermark, "_wm", lambda _a: ".png"),
    "optimize": (op_optimize, "_opt", lambda a: _FORMAT_EXT.get(a.format.upper(), ".jpg")),
    "dehaze": (op_dehaze, "_dehaze", lambda _a: ".png"),
    "clahe": (op_clahe, "_clahe", lambda _a: ".png"),
    "dither": (op_dither, "_dither", lambda _a: ".png"),
    "distort": (op_distort, "_distort", lambda _a: ".png"),
    "auto-orient": (op_autoorient, "_oriented", lambda _a: ".png"),
    "strip": (op_strip, "_clean", lambda _a: None),
}


def run(args) -> int:
    """Execute the parsed *args*; return a process exit code."""
    if args.command in _MULTI_COMMANDS:
        return _MULTI_COMMANDS[args.command](args)
    paths = iter_image_paths(args.inputs, recursive=args.recursive)
    if not paths:
        print(_NO_INPUTS, file=sys.stderr)
        return 1
    if args.command in _REPORTERS:
        return _report(args, paths, _REPORTERS[args.command])
    return _write(args, paths, *_WRITE_SPEC[args.command])


def _report(args, paths: Sequence[Path], operation) -> int:
    results = [operation(path, args) for path in paths]
    if getattr(args, "json", False):
        print(json.dumps(results, indent=2))
    else:
        for item in results:
            print("  ".join(f"{k}={v}" for k, v in item.items()))
    return 0


def _validated_out_dir(raw: str | None) -> Path | None:
    """Validate the user-supplied --out directory before any filesystem access.

    Rejects parent-traversal (``..``) segments so a crafted argument can't
    escape to an unexpected location (SonarQube python:S6547).
    """
    if not raw:
        return None
    out = Path(raw)
    if ".." in out.parts:
        raise ValueError("--out must not contain '..' path segments")
    return out


def _process_one(src: Path, out_dir, operation, suffix: str, ext_fn, args) -> tuple[str, str]:
    """Process one file; return ``(status, message)`` — pure of shared state."""
    target = output_path(src, str(out_dir) if out_dir else None, suffix, ext_fn(args))
    if args.dry_run:
        return ("dry", f"would write {target}")
    try:
        if out_dir is not None:
            # out_dir is validated (no '..'); writing to a user-chosen directory
            # is the intended CLI behaviour, so the path-escape rule is N/A here.
            out_dir.mkdir(parents=True, exist_ok=True)  # NOSONAR
        if target.exists() and not args.overwrite:
            return ("skip", f"skip (exists): {target}")
        operation(src, target, args)
    except (OSError, ValueError) as exc:
        return ("error", f"error: {src}: {exc}")
    return ("ok", f"{src} -> {target}")


def _resolve_workers(jobs: int, count: int) -> int:
    """Worker count: 1 = inline; 0 = auto; clamp to the number of files."""
    if jobs == 1 or count <= 1:
        return 1
    workers = (os.cpu_count() or 1) if jobs <= 0 else jobs
    return max(1, min(workers, count))


def _write(args, paths: Sequence[Path], operation, suffix: str, ext_fn) -> int:
    try:
        out_dir = _validated_out_dir(args.out)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def work(src: Path) -> tuple[str, str]:
        return _process_one(src, out_dir, operation, suffix, ext_fn, args)

    workers = _resolve_workers(getattr(args, "jobs", 1), len(paths))
    if workers == 1:
        results = [work(src) for src in paths]
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # map preserves input order, so output is deterministic.
            results = list(pool.map(work, paths))

    tally = {"ok": 0, "skip": 0, "error": 0, "dry": 0}
    for status, message in results:
        tally[status] += 1
        print(message, file=sys.stderr if status == "error" else sys.stdout)
    print(f"{tally['ok'] + tally['dry']} processed, {tally['skip']} skipped, "
          f"{tally['error']} errors", file=sys.stderr)
    return 1 if tally["error"] else 0


def _checked_path(raw: str) -> Path:
    """Return *raw* as a Path, rejecting parent-traversal segments (S6547)."""
    path = Path(raw)
    if ".." in path.parts:
        raise ValueError("path must not contain '..' segments")
    return path


def _ensure_parent(out: Path) -> None:
    parent = out.parent
    if str(parent) and not parent.exists():
        # NOSONAR - parent derived from a validated (no '..') CLI path; writing
        # to a user-chosen location is the intended CLI behaviour.
        parent.mkdir(parents=True, exist_ok=True)  # NOSONAR


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
    images = [_load_rgba(p) for p in paths]
    _ensure_parent(out)
    Image.fromarray(build_collage(images, args.columns), mode="RGBA").save(out)
    print(f"{len(paths)} images -> {out}")
    return 0


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
    result = anaglyph(_load_rgba(left), _load_rgba(right), args.method)
    _ensure_parent(out)
    Image.fromarray(result, mode="RGBA").save(out)
    print(f"{left} + {right} -> {out}")
    return 0


def op_preset(src: Path, target: Path, args) -> None:
    Image.fromarray(args.recipe.apply(_load_rgba(src)), mode="RGBA").save(target)


def cmd_preset(args) -> int:
    """Apply a saved develop preset (by name) to each input image."""
    from Imervue.image.develop_presets import PRESETS_KEY, DevelopPresetStore
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    if PRESETS_KEY not in user_setting_dict:
        from Imervue.user_settings.user_setting_dict import read_user_setting
        read_user_setting()
    store = DevelopPresetStore(user_setting_dict)
    recipe = store.get(args.name)
    if recipe is None:
        print(f"unknown preset {args.name!r}; available: {store.names()}", file=sys.stderr)
        return 1
    paths = iter_image_paths(args.inputs, recursive=args.recursive)
    if not paths:
        print(_NO_INPUTS, file=sys.stderr)
        return 1
    args.recipe = recipe
    return _write(args, paths, op_preset, "_preset", lambda _a: ".png")


def cmd_list_ops(args) -> int:
    """List the available subcommands and their one-line help."""
    ops: list[dict] = []
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            ops = [{"command": a.dest, "help": a.help or ""}
                   for a in action._choices_actions]
            break
    if getattr(args, "json", False):
        print(json.dumps(ops, indent=2))
    else:
        for op in ops:
            print(f"{op['command']:14} {op['help']}")
    return 0


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


_MULTI_COMMANDS = {
    "collage": cmd_collage, "anaglyph": cmd_anaglyph,
    "preset": cmd_preset, "pipeline": cmd_pipeline, "list-ops": cmd_list_ops,
}


def _add_common(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("inputs", nargs="+", help="image files or folders")
    sub.add_argument("--out", default=None, help="output directory")
    sub.add_argument("--recursive", action="store_true", help="recurse into folders")
    sub.add_argument("--dry-run", action="store_true", help="list actions, write nothing")
    sub.add_argument("--overwrite", action="store_true", help="overwrite existing outputs")
    sub.add_argument("-j", "--jobs", type=int, default=1,
                     help="parallel workers (1=inline, 0=auto/all cores)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="Imervue.cli", description="Imervue headless image CLI")
    parser.add_argument("--version", action="version", version=f"Imervue CLI {_CLI_VERSION}")
    subs = parser.add_subparsers(dest="command", required=True)

    info = subs.add_parser("info", help="print image dimensions / format")
    _add_common(info)
    info.add_argument("--json", action="store_true", help=_EMIT_JSON)

    stats = subs.add_parser("stats", help="print no-reference quality metrics")
    _add_common(stats)
    stats.add_argument("--json", action="store_true", help=_EMIT_JSON)

    convert = subs.add_parser("convert", help="convert format")
    _add_common(convert)
    convert.add_argument("--format", default="PNG", help="JPEG / PNG / WEBP")
    convert.add_argument("--quality", type=int, default=90, help="1-100 for lossy formats")

    resize = subs.add_parser("resize", help="resize to a maximum long edge")
    _add_common(resize)
    resize.add_argument("--max", type=int, default=1600, help="max long edge in px")

    thumb = subs.add_parser("thumbnail", help="make thumbnails")
    _add_common(thumb)
    thumb.add_argument("--size", type=int, default=256, help="thumbnail box in px")

    watermark = subs.add_parser("watermark", help="apply a text watermark")
    _add_common(watermark)
    watermark.add_argument("--text", required=True, help="watermark text")
    watermark.add_argument("--corner", default="bottom-right", help="placement corner")
    watermark.add_argument("--opacity", type=float, default=0.6, help="0..1")

    optimize = subs.add_parser("optimize", help="encode under a target file size")
    _add_common(optimize)
    optimize.add_argument("--max-kb", type=float, required=True, dest="max_kb")
    optimize.add_argument("--format", default="JPEG", help="JPEG / WEBP")

    dehaze = subs.add_parser("dehaze", help="dark-channel-prior haze removal")
    _add_common(dehaze)
    dehaze.add_argument("--strength", type=float, default=1.0, help="0..1")

    clahe = subs.add_parser("clahe", help="contrast-limited adaptive equalization")
    _add_common(clahe)
    clahe.add_argument("--clip", type=float, default=2.0, help="clip limit")
    clahe.add_argument("--tiles", type=int, default=8, help="tile grid size")

    dither = subs.add_parser("dither", help="ordered (Bayer) dithering")
    _add_common(dither)
    dither.add_argument("--levels", type=int, default=2, help="levels per channel (2-8)")

    distort = subs.add_parser("distort", help="swirl / pinch / ripple")
    _add_common(distort)
    distort.add_argument("--mode", default="swirl", help="swirl / pinch / ripple")
    distort.add_argument("--strength", type=float, default=0.5, help="-1..1")

    orient = subs.add_parser("auto-orient", help="bake EXIF orientation into pixels")
    _add_common(orient)

    strip = subs.add_parser("strip", help="re-save without metadata (EXIF/XMP/ICC)")
    _add_common(strip)

    collage = subs.add_parser("collage", help="composite many images into one grid")
    collage.add_argument("inputs", nargs="+", help="image files or folders")
    collage.add_argument("--recursive", action="store_true")
    collage.add_argument("--columns", type=int, default=3, help="grid columns")
    collage.add_argument("--out", default="collage.png", help="output image file")

    anaglyph = subs.add_parser("anaglyph", help="red-cyan 3D from a stereo pair")
    anaglyph.add_argument("left", help="left-eye image")
    anaglyph.add_argument("right", help="right-eye image")
    anaglyph.add_argument("--method", default="dubois", help="dubois / color / gray / true")
    anaglyph.add_argument("--out", default=None, help="output image file")

    preset = subs.add_parser("preset", help="apply a saved develop preset by name")
    preset.add_argument("name", help="develop preset name")
    _add_common(preset)

    pipeline = subs.add_parser("pipeline", help="apply an ordered JSON pipeline of ops")
    pipeline.add_argument("file", help="pipeline JSON file ([{op, ...}] or {pipeline: [...]})")
    _add_common(pipeline)

    list_ops = subs.add_parser("list-ops", help="list available subcommands")
    list_ops.add_argument("--json", action="store_true", help=_EMIT_JSON)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse *argv* and run the requested sub-command."""
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
