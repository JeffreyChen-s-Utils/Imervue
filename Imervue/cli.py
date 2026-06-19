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
}


def run(args) -> int:
    """Execute the parsed *args*; return a process exit code."""
    paths = iter_image_paths(args.inputs, recursive=args.recursive)
    if not paths:
        print("no input images found", file=sys.stderr)
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


def _write(args, paths: Sequence[Path], operation, suffix: str, ext_fn) -> int:
    try:
        out_dir = _validated_out_dir(args.out)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors = 0
    for src in paths:
        target = output_path(src, str(out_dir) if out_dir else None, suffix, ext_fn(args))
        try:
            if args.dry_run:
                print(f"would write {target}")
                continue
            if out_dir is not None:
                out_dir.mkdir(parents=True, exist_ok=True)
            if target.exists() and not args.overwrite:
                print(f"skip (exists): {target}")
                continue
            operation(src, target, args)
            print(f"{src} -> {target}")
        except (OSError, ValueError) as exc:
            print(f"error: {src}: {exc}", file=sys.stderr)
            errors += 1
    return 1 if errors else 0


def _add_common(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("inputs", nargs="+", help="image files or folders")
    sub.add_argument("--out", default=None, help="output directory")
    sub.add_argument("--recursive", action="store_true", help="recurse into folders")
    sub.add_argument("--dry-run", action="store_true", help="list actions, write nothing")
    sub.add_argument("--overwrite", action="store_true", help="overwrite existing outputs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="Imervue.cli", description="Imervue headless image CLI")
    subs = parser.add_subparsers(dest="command", required=True)

    info = subs.add_parser("info", help="print image dimensions / format")
    _add_common(info)
    info.add_argument("--json", action="store_true", help="emit JSON")

    stats = subs.add_parser("stats", help="print no-reference quality metrics")
    _add_common(stats)
    stats.add_argument("--json", action="store_true", help="emit JSON")

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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse *argv* and run the requested sub-command."""
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
