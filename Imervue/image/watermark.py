"""
Text watermark compositing for exports.

Pure image-math module \u2014 no Qt, no dialog state. Takes a PIL image plus a
``WatermarkOptions`` value and returns a new image with the watermark
rendered at the chosen corner. Designed to be called from the batch export
worker so it stays off the UI thread.

Padding and font sizing are computed as a fraction of the image's long
edge so watermarks scale naturally across a 1080px social post and a
6000px print export.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CORNERS = (
    "top-left", "top-right", "bottom-left", "bottom-right", "center",
)
_DEFAULT_FONT_FRAC = 0.035
_DEFAULT_PADDING_FRAC = 0.02
_MIN_FONT_PX = 12
_MAX_OPACITY = 255


@dataclass
class WatermarkOptions:
    """Describes what / where / how opaque to draw the watermark."""

    text: str = ""
    corner: str = "bottom-right"
    opacity: float = 0.6  # 0..1
    font_fraction: float = _DEFAULT_FONT_FRAC
    color: tuple[int, int, int] = (255, 255, 255)
    shadow: bool = True

    def is_active(self) -> bool:
        return bool(self.text and self.text.strip())


def apply_watermark(img: Image.Image, opts: WatermarkOptions) -> Image.Image:
    """Return a copy of ``img`` with ``opts.text`` rendered on top.

    A no-op returning the original image when ``opts`` carries no text.
    Always works on an RGBA copy so the caller's image is untouched.
    """
    if not opts.is_active():
        return img

    base = img.convert("RGBA")
    long_edge = max(base.size)
    font_px = max(_MIN_FONT_PX, int(long_edge * _clamp(opts.font_fraction, 0.005, 0.2)))
    font = _load_font(font_px)
    padding = int(long_edge * _DEFAULT_PADDING_FRAC)
    alpha = _opacity_to_byte(opts.opacity)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), opts.text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x, y = _position_for(
        corner=opts.corner,
        img_size=base.size,
        text_size=(text_w, text_h),
        padding=padding,
    )
    _draw_text(draw, (x, y), opts, font, alpha)

    return Image.alpha_composite(base, overlay)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _opacity_to_byte(opacity: float) -> int:
    return int(_clamp(opacity, 0.0, 1.0) * _MAX_OPACITY)


def _draw_text(draw, xy, opts: WatermarkOptions, font, alpha: int) -> None:
    """Paint the text (with optional drop shadow) onto the overlay."""
    x, y = xy
    if opts.shadow:
        shadow_alpha = min(alpha, int(_MAX_OPACITY * 0.7))
        draw.text((x + 2, y + 2), opts.text, font=font, fill=(0, 0, 0, shadow_alpha))
    draw.text((x, y), opts.text, font=font, fill=(*opts.color, alpha))


def _position_for(
    corner: str,
    img_size: tuple[int, int],
    text_size: tuple[int, int],
    padding: int,
) -> tuple[int, int]:
    """Compute the top-left corner for ``text_size`` inside an image."""
    img_w, img_h = img_size
    text_w, text_h = text_size
    if corner == "top-left":
        return padding, padding
    if corner == "top-right":
        return img_w - text_w - padding, padding
    if corner == "bottom-left":
        return padding, img_h - text_h - padding
    if corner == "center":
        return (img_w - text_w) // 2, (img_h - text_h) // 2
    # bottom-right is the sensible default
    return img_w - text_w - padding, img_h - text_h - padding


def _load_font(size_px: int):
    """Try common TrueType fonts, falling back to PIL's default bitmap font."""
    for candidate in _candidate_font_paths():
        try:
            return ImageFont.truetype(str(candidate), size_px)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


def _candidate_font_paths() -> list[Path]:
    """Return plausible font paths across Windows / macOS / Linux."""
    return [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ]
