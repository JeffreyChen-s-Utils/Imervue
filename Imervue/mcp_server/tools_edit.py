"""Write-side MCP tool handlers: overlays, geometry and effects saved to a destination.

Every handler reads ``source``, writes ``destination`` and returns a
JSON-serialisable summary. Registered through
:data:`Imervue.mcp_server.tool_defs_edit.EDIT_TOOL_DEFINITIONS`.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from Imervue.mcp_server.tool_support import (
    NO_ALPHA_FORMATS,
    load_rgba_array,
    open_upright,
    validated_file,
)

# Ceiling on any generated output buffer. The server runs synchronously with
# no per-request memory limit and does no JSON-schema validation of arguments,
# so an unclamped 50000x50000 target would try to allocate ~10 GB and block
# every other request. 100 MP comfortably covers legitimate large exports.
_MAX_OUTPUT_PIXELS = 100_000_000
_RGB_MAX = 255
_DEFAULT_WATERMARK_COLOR = (_RGB_MAX, _RGB_MAX, _RGB_MAX)
_DEFAULT_FRAME_TEXT_COLOR = (40, 40, 40)
_WATERMARK_CORNERS = frozenset({
    "top-left", "top-right", "bottom-left", "bottom-right", "center",
})


# ---------------------------------------------------------------------------
# apply_watermark
# ---------------------------------------------------------------------------


def _validated_rgb_triplet(
    color: Any, default: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Coerce a JSON ``[r, g, b]`` array into a clamped uint8 RGB tuple."""
    if color is None:
        return default
    if (not isinstance(color, list | tuple) or len(color) != 3
            or not all(isinstance(c, int) for c in color)):
        raise ValueError("color must be a list of three integers 0-255")
    return tuple(max(0, min(_RGB_MAX, int(c))) for c in color)


def _save_image_to(dst: Path, img: Any) -> None:
    """Save a PIL image to ``dst``, flattening alpha for formats lacking it."""
    fmt = dst.suffix.lower().lstrip(".")
    to_save = img.convert("RGB") if fmt in NO_ALPHA_FORMATS else img
    to_save.save(dst)


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
    framed = add_frame(load_rgba_array(src), opts)
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


def _validated_destination(destination: str) -> Path:
    """Return the destination Path, requiring its parent directory to exist."""
    dst = Path(destination)
    if not dst.parent.exists():
        raise ValueError(f"destination parent {dst.parent} does not exist")
    return dst


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


def _guard_output_pixels(width: int, height: int) -> None:
    """Reject absurd output geometry before allocating the buffer."""
    if width * height > _MAX_OUTPUT_PIXELS:
        raise ValueError(
            f"output {width}x{height} exceeds the "
            f"{_MAX_OUTPUT_PIXELS}-pixel limit",
        )


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


# ---------------------------------------------------------------------------
# solarize_image
# ---------------------------------------------------------------------------


def _apply_effect_and_save(
    source: str, destination: str, transform: Callable[[Any], Any],
) -> dict[str, Any]:
    """Load *source* as RGBA, run *transform*, save to *destination*, report stats.

    The shared body of every "apply one effect and save a copy" tool: returns the
    source and destination paths, the result dimensions and the file size.
    """
    from PIL import Image

    src = validated_file(source)
    dst = _validated_destination(destination)
    result = transform(load_rgba_array(src))
    height, width = int(result.shape[0]), int(result.shape[1])
    _save_image_to(dst, Image.fromarray(result, mode="RGBA"))
    return {
        "source": str(src),
        "destination": str(dst),
        "width": width,
        "height": height,
        "size_bytes": int(dst.stat().st_size),
    }


def solarize_image(
    source: str,
    destination: str,
    *,
    threshold: float = 0.5,
    mix: float = 1.0,
) -> dict[str, Any]:
    """Apply a solarize tone reversal to ``source`` and save it to ``destination``.

    Tones at or above ``threshold`` (0-1) are inverted; ``mix`` (0-1) blends the
    result toward the original.
    """
    from Imervue.image.solarize import apply_solarize
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_solarize(arr, float(threshold), float(mix)),
    )


# ---------------------------------------------------------------------------
# glow_image
# ---------------------------------------------------------------------------


def glow_image(
    source: str,
    destination: str,
    *,
    amount: float = 0.5,
    radius: int = 15,
    threshold: float = 0.0,
) -> dict[str, Any]:
    """Apply a diffuse-glow / Orton bloom to ``source`` and save to ``destination``.

    ``amount`` (0-1) is the glow opacity, ``radius`` the blur radius and
    ``threshold`` (0-1) the brightness above which regions bloom (0 = whole frame).
    """
    from Imervue.image.glow import apply_glow
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_glow(arr, float(amount), int(radius), float(threshold)),
    )


# ---------------------------------------------------------------------------
# tonal / colour effects
# ---------------------------------------------------------------------------


def velvia_image(
    source: str, destination: str, *,
    strength: float = 1.0, luminance_protection: float = 0.5,
) -> dict[str, Any]:
    """Apply a Velvia luminance-weighted saturation boost and save the result."""
    from Imervue.image.velvia import apply_velvia
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_velvia(arr, float(strength), float(luminance_protection)),
    )


def emboss_image(
    source: str, destination: str, *,
    azimuth_deg: float = 135.0, elevation_deg: float = 45.0,
    depth: float = 1.0, grayscale: bool = True,
) -> dict[str, Any]:
    """Apply a directional-light emboss relief and save the result."""
    from Imervue.image.emboss import apply_emboss
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_emboss(
            arr, float(azimuth_deg), float(elevation_deg), float(depth), bool(grayscale),
        ),
    )


def film_negative_image(
    source: str, destination: str, *, gamma: float = 1.0,
) -> dict[str, Any]:
    """Invert a scanned colour negative (auto film base) and save the positive."""
    from Imervue.image.film_negative import apply_film_negative
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_film_negative(arr, None, float(gamma)),
    )


def defringe_image(
    source: str, destination: str, *,
    amount: float = 1.0, edge_threshold: float = 0.1, hue: str = "purple",
) -> dict[str, Any]:
    """Desaturate purple/green chromatic-aberration edge fringes and save the result."""
    from Imervue.image.defringe import apply_defringe
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_defringe(arr, float(amount), float(edge_threshold), str(hue)),
    )


def graduated_density_image(
    source: str, destination: str, *,
    angle_deg: float = 0.0, density_stops: float = 1.0,
    hardness: float = 0.5, offset: float = 0.0,
) -> dict[str, Any]:
    """Apply a linear graduated neutral-density gradient and save the result."""
    from Imervue.image.graduated_density import apply_graduated_density
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_graduated_density(
            arr, float(angle_deg), float(density_stops), float(hardness), float(offset),
        ),
    )


def filmic_tonemap_image(
    source: str, destination: str, *,
    exposure: float = 0.0, white_point: float = 4.0,
    contrast: float = 1.0, saturation: float = 1.0, mode: str = "reinhard",
) -> dict[str, Any]:
    """Apply a filmic (Reinhard/Hable) tone-map highlight rolloff and save the result."""
    from Imervue.image.filmic_tonemap import apply_filmic_tonemap
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_filmic_tonemap(
            arr, float(exposure), float(white_point),
            float(contrast), float(saturation), str(mode),
        ),
    )


_TONE_EQ_DEFAULT = (0.0, 0.0, 0.0, 0.0, 0.0)
_DETAIL_EQ_DEFAULT = (1.0, 1.0, 1.0, 1.0)


def tone_equalizer_image(
    source: str, destination: str, *,
    zone_gains: list[float] | None = None, smoothing: int = 12,
) -> dict[str, Any]:
    """Apply per-luminance-zone exposure (shadows to highlights) and save the result."""
    from Imervue.image.tone_equalizer import apply_tone_equalizer
    gains = tuple(float(g) for g in (zone_gains if zone_gains is not None else _TONE_EQ_DEFAULT))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_tone_equalizer(arr, gains, int(smoothing)),
    )


def detail_equalizer_image(
    source: str, destination: str, *, band_gains: list[float] | None = None,
) -> dict[str, Any]:
    """Re-weight contrast per detail band (finest to coarsest, 1.0 neutral) and save."""
    from Imervue.image.detail_equalizer import apply_detail_equalizer
    gains = tuple(float(g) for g in (band_gains if band_gains is not None else _DETAIL_EQ_DEFAULT))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_detail_equalizer(arr, gains),
    )


# ---------------------------------------------------------------------------
# stylize / artistic effects
# ---------------------------------------------------------------------------


def colormap_image(
    source: str, destination: str, *, name: str = "viridis",
) -> dict[str, Any]:
    """Re-colour ``source`` luminance through a named colour map and save the result."""
    from Imervue.image.colormap import apply_colormap
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_colormap(arr, str(name)),
    )


def false_color_image(source: str, destination: str) -> dict[str, Any]:
    """Map ``source`` luminance to a false-colour exposure scale and save the result."""
    from Imervue.image.false_color import false_color
    return _apply_effect_and_save(source, destination, false_color)


def dither_image(
    source: str, destination: str, *, levels: int = 2,
) -> dict[str, Any]:
    """Ordered-dither ``source`` to ``levels`` tones per channel and save the result."""
    from Imervue.image.dither import ordered_dither
    return _apply_effect_and_save(
        source, destination,
        lambda arr: ordered_dither(arr, int(levels)),
    )


def split_toning_image(
    source: str, destination: str, *,
    shadow_hue: float = 210.0, shadow_saturation: float = 0.0,
    highlight_hue: float = 45.0, highlight_saturation: float = 0.0,
    balance: float = 0.0,
) -> dict[str, Any]:
    """Tint shadows and highlights with separate hues weighted by luminance, then save."""
    from Imervue.image.split_toning import apply_split_toning
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_split_toning(
            arr, float(shadow_hue), float(shadow_saturation),
            float(highlight_hue), float(highlight_saturation), float(balance),
        ),
    )


def pixel_sort_image(
    source: str, destination: str, *,
    lower: int = 60, upper: int = 200, vertical: bool = False,
) -> dict[str, Any]:
    """Sort pixels within brightness bands (``lower``-``upper``) and save the result."""
    from Imervue.image.pixel_sort import pixel_sort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: pixel_sort(arr, int(lower), int(upper), vertical=bool(vertical)),
    )


# ---------------------------------------------------------------------------
# geometric / detail effects
# ---------------------------------------------------------------------------


def polar_image(
    source: str, destination: str, *,
    to_polar: bool = True, invert: bool = False,
) -> dict[str, Any]:
    """Warp ``source`` between rectangular and polar coordinates and save the result."""
    from Imervue.image.polar import polar_distort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: polar_distort(arr, bool(to_polar), bool(invert)),
    )


def kaleidoscope_image(
    source: str, destination: str, *,
    segments: int = 6, angle_deg: float = 0.0,
) -> dict[str, Any]:
    """Mirror ``source`` into ``segments`` kaleidoscope wedges and save the result."""
    import math

    from Imervue.image.kaleidoscope import kaleidoscope
    angle_offset = math.radians(float(angle_deg))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: kaleidoscope(arr, int(segments), None, angle_offset),
    )


def frosted_glass_image(
    source: str, destination: str, *, radius: int = 4, seed: int = 0,
) -> dict[str, Any]:
    """Scatter each pixel to a random neighbour within ``radius`` and save the result."""
    from Imervue.image.frosted_glass import frosted_glass
    return _apply_effect_and_save(
        source, destination,
        lambda arr: frosted_glass(arr, int(radius), int(seed)),
    )


def clahe_image(
    source: str, destination: str, *,
    clip_limit: float = 2.0, tiles: int = 8,
) -> dict[str, Any]:
    """Apply contrast-limited adaptive histogram equalization and save the result."""
    from Imervue.image.clahe import apply_clahe
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_clahe(arr, float(clip_limit), int(tiles)),
    )


def local_contrast_image(
    source: str, destination: str, *,
    clarity: float = 0.0, texture: float = 0.0,
) -> dict[str, Any]:
    """Add midtone clarity and fine-detail texture local contrast, then save."""
    from Imervue.image.local_contrast import apply_clarity, apply_texture
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_texture(apply_clarity(arr, float(clarity)), float(texture)),
    )


# ---------------------------------------------------------------------------
# tone-grading / lens effects
# ---------------------------------------------------------------------------


def posterize_image(
    source: str, destination: str, *, levels: int = 4,
) -> dict[str, Any]:
    """Quantize each channel to ``levels`` discrete steps and save the result."""
    from Imervue.image.posterize import PosterizeOptions, apply_posterize
    options = PosterizeOptions(enabled=True, levels=int(levels))
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_posterize(arr, options),
    )


def gradient_map_image(
    source: str, destination: str, *,
    intensity: float = 1.0, perceptual: bool = False,
) -> dict[str, Any]:
    """Map luminance through a black-to-white gradient and save the blended result."""
    from Imervue.image.gradient_map import GradientMapOptions, apply_gradient_map
    options = GradientMapOptions(
        enabled=True, intensity=float(intensity), perceptual=bool(perceptual),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_gradient_map(arr, options),
    )


def film_grain_image(
    source: str, destination: str, *,
    intensity: float = 0.25, size: int = 1,
    monochrome: bool = True, seed: int = 0,
) -> dict[str, Any]:
    """Add tunable Gaussian film grain to the image and save the result."""
    from Imervue.image.film_grain import FilmGrainOptions, apply_film_grain
    options = FilmGrainOptions(
        enabled=True, intensity=float(intensity), size=int(size),
        monochrome=bool(monochrome), seed=int(seed),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_film_grain(arr, options),
    )


def dehaze_image(
    source: str, destination: str, *, strength: float = 0.5,
) -> dict[str, Any]:
    """Remove atmospheric haze (dark-channel prior) by ``strength`` and save."""
    from Imervue.image.dehaze import dehaze
    return _apply_effect_and_save(
        source, destination,
        lambda arr: dehaze(arr, float(strength)),
    )


def distort_image(
    source: str, destination: str, *,
    mode: str = "swirl", strength: float = 0.5,
) -> dict[str, Any]:
    """Warp the image with a swirl, pinch or ripple distortion and save the result."""
    from Imervue.image.distort import distort
    return _apply_effect_and_save(
        source, destination,
        lambda arr: distort(arr, str(mode), float(strength)),
    )


# ---------------------------------------------------------------------------
# colour-grading / curve effects
# ---------------------------------------------------------------------------


def levels_image(
    source: str, destination: str, *,
    black: int = 0, white: int = 255, gamma: float = 1.0,
) -> dict[str, Any]:
    """Remap tones with input black/white points and a gamma, then save."""
    from Imervue.image.levels import LevelsOptions, apply_levels
    options = LevelsOptions(
        enabled=True, black=int(black), white=int(white), gamma=float(gamma),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_levels(arr, options),
    )


def auto_color_balance_image(
    source: str, destination: str, *,
    method: str = "percentile_stretch", intensity: float = 1.0,
    percentile: float = 1.0, retinex_radius: int = 24,
) -> dict[str, Any]:
    """Auto white-balance / colour-cast correction by the chosen method, then save."""
    from Imervue.image.auto_color_balance import AutoBalanceOptions, auto_balance
    options = AutoBalanceOptions(
        method=str(method), intensity=float(intensity),
        percentile=float(percentile), retinex_radius=int(retinex_radius),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: auto_balance(arr, options),
    )


def channel_mixer_image(
    source: str, destination: str, *,
    red: list[float] | None = None, green: list[float] | None = None,
    blue: list[float] | None = None, offsets: list[float] | None = None,
    monochrome: bool = False,
) -> dict[str, Any]:
    """Remix output channels from a 3x3 weight matrix plus offsets, then save."""
    from Imervue.image.channel_mixer import ChannelMixerOptions, apply_channel_mixer
    options = ChannelMixerOptions(
        enabled=True,
        red=[float(v) for v in (red if red is not None else [1.0, 0.0, 0.0])],
        green=[float(v) for v in (green if green is not None else [0.0, 1.0, 0.0])],
        blue=[float(v) for v in (blue if blue is not None else [0.0, 0.0, 1.0])],
        offsets=[float(v) for v in (offsets if offsets is not None else [0.0, 0.0, 0.0])],
        monochrome=bool(monochrome),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_channel_mixer(arr, options),
    )


_CURVE_PRESETS = ("s_curve", "lift_shadows", "compress_highlights")


def _curve_points(preset: str, strength: float):
    """Return the master-curve points for a named preset."""
    from Imervue.image import curves
    builders = {
        "s_curve": curves.s_curve_preset,
        "lift_shadows": curves.lift_shadows_preset,
        "compress_highlights": curves.compress_highlights_preset,
    }
    builder = builders.get(preset)
    if builder is None:
        raise ValueError(
            f"unknown curve preset {preset!r}; expected one of {_CURVE_PRESETS}",
        )
    return builder(strength)


def curve_image(
    source: str, destination: str, *,
    preset: str = "s_curve", strength: float = 0.15,
) -> dict[str, Any]:
    """Apply a tone-curve preset (S-curve, lift shadows, compress highlights), then save."""
    from Imervue.image.curves import CurveOptions, apply_curves
    options = CurveOptions(
        enabled=True, per_channel={"rgb": _curve_points(str(preset), float(strength))},
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_curves(arr, options),
    )


def lens_correction_image(
    source: str, destination: str, *,
    k1: float = 0.0, vignette: float = 0.0,
    ca_red: float = 0.0, ca_blue: float = 0.0,
) -> dict[str, Any]:
    """Correct barrel/pincushion distortion, vignette and chromatic aberration, then save."""
    from Imervue.image.lens_correction import (
        LensCorrectionOptions,
        apply_lens_correction,
    )
    options = LensCorrectionOptions(
        k1=float(k1), vignette=float(vignette),
        ca_red=float(ca_red), ca_blue=float(ca_blue),
    )
    return _apply_effect_and_save(
        source, destination,
        lambda arr: apply_lens_correction(arr, options),
    )


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------
