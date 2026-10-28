"""Native image writer adapters with the viewer decoding policy."""
from __future__ import annotations

import numpy as np
from PIL import Image
from collections.abc import Sequence
from pathlib import Path
from Imervue.image.high_bit_depth import to_eight_bit
from Imervue.image.shown import load_shown_rgba, open_shown


_FORMAT_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


_RGB_MAX = 255


def _resize_to(img: Image.Image, max_edge: int) -> Image.Image:
    resized = img.copy()
    resized.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return resized


def _rgb(values: Sequence[int]) -> tuple[int, int, int]:
    """An ``R G B`` option clamped to 0..255."""
    return tuple(max(0, min(_RGB_MAX, int(v))) for v in values)


def op_convert(src: Path, target: Path, args) -> None:
    fmt = args.format.upper()
    if fmt not in _FORMAT_EXT:   # TIFF, BMP, AVIF, HEIC, JXL: the MCP tool's writer
        from Imervue.mcp_server.tools_read import convert_format
        convert_format(str(src), str(target), quality=args.quality)
        return
    img = to_eight_bit(open_shown(src))   # 16-bit / float grey scaled, not clipped white
    rgb = img.convert("RGB") if fmt == "JPEG" else img.convert("RGBA")
    rgb.save(target, format=fmt, quality=args.quality)


def op_resize(src: Path, target: Path, args) -> None:
    if args.width is not None or args.height is not None:
        from Imervue.mcp_server.tools_edit import resize_image   # exact, or one edge kept in aspect
        resize_image(str(src), str(target), width=args.width, height=args.height)
        return
    _resize_to(open_shown(src), args.max).save(target)


def op_thumbnail(src: Path, target: Path, args) -> None:
    _resize_to(to_eight_bit(open_shown(src)).convert("RGBA"), args.size).save(target)


def op_watermark(src: Path, target: Path, args) -> None:
    from Imervue.image.watermark import WatermarkOptions, apply_watermark
    apply_watermark(to_eight_bit(open_shown(src)).convert("RGBA"), WatermarkOptions(
        text=args.text, corner=args.corner, opacity=args.opacity,
        font_fraction=args.font_fraction, color=_rgb(args.color),
        shadow=args.shadow)).save(target)


def op_optimize(src: Path, target: Path, args) -> None:
    from Imervue.image.optimize import encode_to_budget
    data, _quality = encode_to_budget(load_shown_rgba(src), args.max_kb, args.format.upper())
    target.write_bytes(data)


def op_dehaze(src: Path, target: Path, args) -> None:
    from Imervue.image.dehaze import dehaze
    Image.fromarray(dehaze(load_shown_rgba(src), args.strength), mode="RGBA").save(target)


def op_clahe(src: Path, target: Path, args) -> None:
    from Imervue.image.clahe import apply_clahe
    clahe = apply_clahe(load_shown_rgba(src), args.clip, args.tiles)
    Image.fromarray(clahe, mode="RGBA").save(target)


def op_dither(src: Path, target: Path, args) -> None:
    from Imervue.image.dither import ordered_dither
    Image.fromarray(ordered_dither(load_shown_rgba(src), args.levels), mode="RGBA").save(target)


def op_distort(src: Path, target: Path, args) -> None:
    from Imervue.image.distort import distort
    distorted = distort(load_shown_rgba(src), args.mode, args.strength)
    Image.fromarray(distorted, mode="RGBA").save(target)


def op_painterly(src: Path, target: Path, args) -> None:
    """Repaint *src* in oil-paint brush strokes; the source's alpha is kept."""
    from Imervue.paint.painterly import PainterlyOptions, paint
    rgba = load_shown_rgba(src)
    painted = paint(rgba, PainterlyOptions(seed=args.seed))
    Image.fromarray(np.dstack([painted, rgba[..., 3]]), mode="RGBA").save(target)


def op_autoorient(src: Path, target: Path, _args) -> None:
    Image.fromarray(load_shown_rgba(src), mode="RGBA").save(target)


def op_strip(src: Path, target: Path, _args) -> None:
    # Re-save without forwarding exif/icc/xmp — Pillow omits metadata by default.
    # The orientation and colour profile go with them, so bake both in first.
    image = open_shown(src)
    image.info.clear()
    image.save(target)
