"""
Export presets \u2014 named bundles of resize / format / quality settings that
cover the common publishing targets (web upload, print submission, IG).

Consumers call ``get_preset(name)`` to retrieve an ``ExportPreset`` and
then apply it to their dialog UI. Keeping the catalogue here (instead of
hard-coding the values inside the dialog) lets batch scripts, macros, and
the one-shot export dialog all share the same definitions.
"""
from __future__ import annotations

from dataclasses import dataclass

_JPEG = "JPEG"
_PNG = "PNG"


@dataclass(frozen=True)
class ExportPreset:
    """Preset values applied to the batch export dialog when chosen."""

    key: str
    label: str          # human-readable label (already localised)
    format: str
    quality: int        # 1..100 (ignored for lossless formats)
    max_width: int      # 0 means "do not resize on this axis"
    max_height: int
    dpi: int = 0        # 0 means "leave DPI untouched"
    square_crop: bool = False  # if True, crop to a square before resize


def builtin_presets() -> list[ExportPreset]:
    """Return the default preset catalogue in display order."""
    return [
        ExportPreset(
            key="web_1600",
            label="Web \u2014 1600 px JPEG",
            format=_JPEG,
            quality=85,
            max_width=1600,
            max_height=1600,
        ),
        ExportPreset(
            key="web_3840",
            label="4K Web \u2014 3840 px JPEG",
            format=_JPEG,
            quality=90,
            max_width=3840,
            max_height=3840,
        ),
        ExportPreset(
            key="print_300dpi",
            label="Print \u2014 300 DPI PNG",
            format=_PNG,
            quality=100,
            max_width=0,
            max_height=0,
            dpi=300,
        ),
        ExportPreset(
            key="instagram_1080",
            label="Instagram \u2014 1080\u00d71080 square",
            format=_JPEG,
            quality=90,
            max_width=1080,
            max_height=1080,
            square_crop=True,
        ),
        ExportPreset(
            key="thumbnail_400",
            label="Thumbnail \u2014 400 px JPEG",
            format=_JPEG,
            quality=80,
            max_width=400,
            max_height=400,
        ),
    ]


def get_preset(key: str) -> ExportPreset | None:
    """Return the preset matching ``key`` or ``None`` if not found."""
    for preset in builtin_presets():
        if preset.key == key:
            return preset
    return None


def square_crop(img):
    """Centre-crop a PIL image to its shortest-edge square."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))
