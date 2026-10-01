"""Helpers shared by the MCP tool handlers in ``tools_read`` and ``tools_edit``.

Argument validation, JSON coercion of EXIF values and the image-loading and
format constants both handler groups use. Qt-free like the rest of the server.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from Imervue.image.formats import RASTER_EXTENSIONS

# Image extensions the listing tools consider: the viewer's still formats but
# SVG, which needs Qt to rasterise and the server is Qt-free.
IMAGE_EXTENSIONS: frozenset[str] = RASTER_EXTENSIONS
# Destination formats that can't carry alpha — flatten to RGB before saving.
NO_ALPHA_FORMATS = frozenset({"jpg", "jpeg", "bmp"})


def open_upright(image_path: Path):
    """Open *image_path* decoded, converted to sRGB and turned upright.

    Every tool works on the image as a viewer shows it: sizes, crop boxes and
    the written copies (which carry no EXIF or ICC) all use these pixels. A
    camera RAW is developed, not read as its embedded preview
    (:func:`Imervue.image.shown.open_shown`).
    """
    from Imervue.image.shown import open_shown
    return open_shown(image_path)


def load_rgba_array(image_path: Path):
    """Load *image_path* as an upright HxWx4 uint8 RGBA array."""
    from Imervue.image.shown import load_shown_rgba
    return load_shown_rgba(image_path)


def validated_dir(path: str) -> Path:
    """Return *path* as an existing directory, or raise ``ValueError``."""
    if not isinstance(path, str) or not path:
        raise ValueError("folder must be a non-empty string")
    candidate = Path(path).expanduser()
    if not candidate.is_dir():
        raise ValueError(f"folder {candidate} does not exist")
    return candidate


def validated_file(path: str) -> Path:
    """Return *path* as an existing file, or raise ``ValueError``."""
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise ValueError(f"file {candidate} does not exist")
    return candidate


def json_safe(value: Any) -> Any:
    """Coerce EXIF / Pillow values into JSON-serialisable forms.

    Bytes become hex (so the client can still see the data without
    binary-in-JSON issues); IFDRational becomes a float; tuples become
    lists; everything else falls back to ``str(value)``."""
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list | tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    # PIL's IFDRational / Fraction exposes numerator / denominator.
    num = getattr(value, "numerator", None)
    den = getattr(value, "denominator", None)
    if num is not None and den:
        return float(num) / float(den)
    return str(value)
