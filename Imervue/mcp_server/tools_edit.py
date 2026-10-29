"""Write-side MCP tool handlers: overlays, geometry and effects saved to a destination.

Every handler reads ``source``, writes ``destination`` and returns a
JSON-serialisable summary. Registered through
:data:`Imervue.mcp_server.tool_defs_edit.EDIT_TOOL_DEFINITIONS`.

The overlay and geometry handlers live here; the effect handlers live in
``tools_edit_effects`` and ``tools_edit_grading`` and the shared validation /
save helpers in ``tools_edit_support``. All are re-exported from this module,
which stays the import location for the tool definitions and the CLI.
"""
from __future__ import annotations

from typing import Any

from Imervue.mcp_server.tool_support import (
    load_rgba_array,
    open_upright,
    validated_file,
)
from Imervue.mcp_server.tools_edit_effects import (
    clahe_image,
    colormap_image,
    defringe_image,
    detail_equalizer_image,
    dither_image,
    emboss_image,
    false_color_image,
    film_negative_image,
    filmic_tonemap_image,
    frosted_glass_image,
    glow_image,
    graduated_density_image,
    kaleidoscope_image,
    local_contrast_image,
    pixel_sort_image,
    polar_image,
    solarize_image,
    split_toning_image,
    tone_equalizer_image,
    velvia_image,
)
from Imervue.mcp_server.tools_edit_grading import (
    auto_color_balance_image,
    channel_mixer_image,
    curve_image,
    dehaze_image,
    distort_image,
    film_grain_image,
    gradient_map_image,
    lens_correction_image,
    levels_image,
    posterize_image,
)
from Imervue.mcp_server.tools_edit_support import (
    _DEFAULT_FRAME_TEXT_COLOR,
    _DEFAULT_WATERMARK_COLOR,
    _guard_output_pixels,
    _save_image_to,
    _validated_destination,
    _validated_rgb_triplet,
)

__all__ = [
    "apply_frame",
    "apply_watermark",
    "auto_color_balance_image",
    "build_collage",
    "channel_mixer_image",
    "clahe_image",
    "colormap_image",
    "crop_image",
    "curve_image",
    "defringe_image",
    "dehaze_image",
    "detail_equalizer_image",
    "distort_image",
    "dither_image",
    "emboss_image",
    "false_color_image",
    "film_grain_image",
    "film_negative_image",
    "filmic_tonemap_image",
    "frosted_glass_image",
    "glow_image",
    "gradient_map_image",
    "graduated_density_image",
    "kaleidoscope_image",
    "lens_correction_image",
    "levels_image",
    "local_contrast_image",
    "pixel_sort_image",
    "polar_image",
    "posterize_image",
    "resize_image",
    "rotate_image",
    "solarize_image",
    "split_toning_image",
    "tone_equalizer_image",
    "velvia_image",
]

_WATERMARK_CORNERS = frozenset({
    "top-left", "top-right", "bottom-left", "bottom-right", "center",
})


# ---------------------------------------------------------------------------
# apply_watermark
# ---------------------------------------------------------------------------


def apply_watermark(
    source: str,
    destination: str,
    text: str,
    *,
    corner: str = "bottom-right",
    opacity: float = 0.6,
    font_fraction: float = 0.035,
    color: list[int] | None = None,
    shadow: bool = True,
) -> dict[str, Any]:
    """Render a text watermark onto ``source`` and save it to ``destination``.

    The destination format is taken from its suffix; formats that can't carry
    alpha (JPEG / BMP) are flattened to RGB first. Returns the destination
    path, its size in bytes and the corner used.
    """
    src = validated_file(source)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if corner not in _WATERMARK_CORNERS:
        raise ValueError(
            f"corner must be one of {sorted(_WATERMARK_CORNERS)}, got {corner!r}",
        )
    dst = _validated_destination(destination)
    rgb = _validated_rgb_triplet(color, _DEFAULT_WATERMARK_COLOR)
    from Imervue.image.watermark import WatermarkOptions
    from Imervue.image.watermark import apply_watermark as _apply
    opts = WatermarkOptions(
        text=text, corner=corner, opacity=float(opacity),
        font_fraction=float(font_fraction), color=rgb, shadow=bool(shadow),
    )
    with open_upright(src) as opened:
        _save_image_to(dst, _apply(opened, opts))
    return {
        "source": str(src),
        "destination": str(dst),
        "size_bytes": int(dst.stat().st_size),
        "corner": corner,
    }


# ---------------------------------------------------------------------------
# apply_frame
# ---------------------------------------------------------------------------


def apply_frame(
    source: str,
    destination: str,
    *,
    border: int = 40,
    color: list[int] | None = None,
    bottom_extra: int = 0,
    caption: str = "",
    text_color: list[int] | None = None,
) -> dict[str, Any]:
    """Wrap an image in a matte border (+ optional caption) and save it.

    ``border`` is the matte width in pixels, ``bottom_extra`` adds a thicker
    Polaroid-style bottom band, and ``caption`` is burned into that band.
    The destination format follows its suffix. Returns the destination path,
    its size in bytes and the framed dimensions.
    """
    src = validated_file(source)
    dst = _validated_destination(destination)
    frame_rgb = _validated_rgb_triplet(color, _DEFAULT_WATERMARK_COLOR)
    text_rgb = _validated_rgb_triplet(text_color, _DEFAULT_FRAME_TEXT_COLOR)
    from PIL import Image
    from Imervue.image.photo_frame import FrameOptions, add_frame
    opts = FrameOptions(
        border=max(0, int(border)), color=frame_rgb,
        bottom_extra=max(0, int(bottom_extra)),
        caption=str(caption), text_color=text_rgb,
    )
    rgba = load_rgba_array(src)
    height, width = rgba.shape[:2]
    _guard_output_pixels(width + opts.border * 2,
                         height + opts.border * 2 + opts.bottom_extra)
    framed = add_frame(rgba, opts)
    with Image.fromarray(framed, "RGBA") as out:
        _save_image_to(dst, out)
    height, width = framed.shape[:2]
    return {
        "source": str(src),
        "destination": str(dst),
        "size_bytes": int(dst.stat().st_size),
        "width": int(width),
        "height": int(height),
    }


# ---------------------------------------------------------------------------
# build_collage
# ---------------------------------------------------------------------------

_COLLAGE_MAX_IMAGES = 200


def build_collage(
    sources: list[str],
    destination: str,
    *,
    columns: int = 3,
    cell_width: int = 400,
    cell_height: int = 400,
    gap: int = 12,
    margin: int = 20,
    background: list[int] | None = None,
    progress: Any = None,
) -> dict[str, Any]:
    """Composite several images into a grid montage and save it.

    Each source is letterboxed and centred in an equal ``cell_width`` x
    ``cell_height`` cell; ``gap`` separates cells and ``margin`` frames the
    grid. The destination format follows its suffix. Returns the destination
    path, image count, column count, output dimensions and size in bytes.

    ``progress`` is an optional reporter injected by the server when the
    caller passes a progressToken; each loaded source advances it.
    """
    if not isinstance(sources, list | tuple) or not sources:
        raise ValueError("sources must be a non-empty list of image paths")
    if len(sources) > _COLLAGE_MAX_IMAGES:
        raise ValueError(f"collage supports at most {_COLLAGE_MAX_IMAGES} images")
    dst = _validated_destination(destination)
    rgb = _validated_rgb_triplet(background, _DEFAULT_WATERMARK_COLOR)
    # Resolve the geometry and reject an oversized montage BEFORE loading any
    # source (mirrors build_collage's own width/height formula), so a caller
    # asking for 5000px cells across 50 images can't OOM the server.
    cols = max(1, int(columns))
    cell_w, cell_h = max(1, int(cell_width)), max(1, int(cell_height))
    gap_px, margin_px = max(0, int(gap)), max(0, int(margin))
    rows = -(-len(sources) // cols)  # ceil division
    out_w = margin_px * 2 + cols * cell_w + (cols - 1) * gap_px
    out_h = margin_px * 2 + rows * cell_h + (rows - 1) * gap_px
    _guard_output_pixels(out_w, out_h)
    total = len(sources)
    arrays = []
    for index, src in enumerate(sources, start=1):
        arrays.append(load_rgba_array(validated_file(src)))
        if progress is not None:
            progress.report(index, total=total, message=f"loaded {index}/{total}")
    from PIL import Image
    from Imervue.image.collage import build_collage as _build
    collage = _build(
        arrays, cols,
        cell=(cell_w, cell_h),
        gap=gap_px, margin=margin_px, background=rgb,
    )
    with Image.fromarray(collage, "RGBA") as out:
        _save_image_to(dst, out)
    height, width = collage.shape[:2]
    return {
        "destination": str(dst),
        "image_count": len(arrays),
        "columns": cols,
        "width": int(width),
        "height": int(height),
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# crop_image
# ---------------------------------------------------------------------------


def crop_image(
    source: str,
    destination: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Crop a rectangular region out of an image and save it.

    ``x`` / ``y`` are the top-left corner and ``width`` / ``height`` the box
    size, all in source pixels. The box must lie fully inside the image. The
    destination format follows its suffix. Returns the destination path, the
    cropped dimensions and the size in bytes.
    """
    src = validated_file(source)
    dst = _validated_destination(destination)
    left, top = int(x), int(y)
    box_w, box_h = int(width), int(height)
    if box_w <= 0 or box_h <= 0:
        raise ValueError("width and height must be positive")
    if left < 0 or top < 0:
        raise ValueError("x and y must be non-negative")
    with open_upright(src) as opened:
        img_w, img_h = opened.size
        if left + box_w > img_w or top + box_h > img_h:
            raise ValueError(
                f"crop box ({left},{top},{box_w}x{box_h}) exceeds "
                f"image {img_w}x{img_h}",
            )
        _save_image_to(dst, opened.crop((left, top, left + box_w, top + box_h)))
    return {
        "source": str(src),
        "destination": str(dst),
        "width": box_w,
        "height": box_h,
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# resize_image
# ---------------------------------------------------------------------------


def _resize_dims(
    src_w: int, src_h: int, width: int | None, height: int | None,
) -> tuple[int, int]:
    """Resolve a resize target, preserving aspect when one edge is omitted."""
    if width is not None and height is not None:
        return (width, height)
    if width is not None:
        return (width, max(1, round(src_h * (width / src_w))))
    return (max(1, round(src_w * (height / src_h))), height)


def resize_image(
    source: str,
    destination: str,
    *,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Resize an image and save it.

    Pass both ``width`` and ``height`` for an exact resize, or just one to
    scale the other proportionally. The destination format follows its
    suffix. Returns the destination path, the new dimensions and size in bytes.
    """
    src = validated_file(source)
    dst = _validated_destination(destination)
    target_w = None if width is None else int(width)
    target_h = None if height is None else int(height)
    if target_w is None and target_h is None:
        raise ValueError("at least one of width or height is required")
    if (target_w is not None and target_w <= 0) or (
        target_h is not None and target_h <= 0
    ):
        raise ValueError("width and height must be positive")
    from PIL import Image
    with open_upright(src) as opened:
        src_w, src_h = opened.size
        target = _resize_dims(src_w, src_h, target_w, target_h)
        _guard_output_pixels(*target)
        _save_image_to(dst, opened.resize(target, Image.Resampling.LANCZOS))
    return {
        "source": str(src),
        "destination": str(dst),
        "width": target[0],
        "height": target[1],
        "size_bytes": int(dst.stat().st_size),
    }


# ---------------------------------------------------------------------------
# rotate_image
# ---------------------------------------------------------------------------

# Operation name -> PIL transpose attribute. Rotations are clockwise; PIL's
# ROTATE_n constants are counter-clockwise, hence the 90/270 swap.
_ROTATE_OPERATIONS: dict[str, str] = {
    "rotate_90": "ROTATE_270",
    "rotate_180": "ROTATE_180",
    "rotate_270": "ROTATE_90",
    "flip_horizontal": "FLIP_LEFT_RIGHT",
    "flip_vertical": "FLIP_TOP_BOTTOM",
}


def rotate_image(source: str, destination: str, operation: str) -> dict[str, Any]:
    """Rotate (clockwise) or flip an image by a fixed operation and save it.

    ``operation`` is one of ``rotate_90`` / ``rotate_180`` / ``rotate_270`` /
    ``flip_horizontal`` / ``flip_vertical``. These are lossless orientation
    changes. The destination format follows its suffix. Returns the
    destination path, the operation, the resulting dimensions and size.
    """
    src = validated_file(source)
    dst = _validated_destination(destination)
    transpose_name = _ROTATE_OPERATIONS.get(operation)
    if transpose_name is None:
        raise ValueError(
            f"operation must be one of {sorted(_ROTATE_OPERATIONS)}, "
            f"got {operation!r}",
        )
    from PIL import Image
    with open_upright(src) as opened:
        result = opened.transpose(getattr(Image.Transpose, transpose_name))
        width, height = result.size
        _save_image_to(dst, result)
    return {
        "source": str(src),
        "destination": str(dst),
        "operation": operation,
        "width": int(width),
        "height": int(height),
        "size_bytes": int(dst.stat().st_size),
    }
