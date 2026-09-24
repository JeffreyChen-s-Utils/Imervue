"""Helpers shared by the MCP tool handlers in ``tools_read`` and ``tools_edit``.

Argument validation, JSON coercion of EXIF values and the image-loading and
format constants both handler groups use. Qt-free like the rest of the server.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Image extensions the listing helper considers (lower-case, with dot).
IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
    ".gif", ".heic", ".heif", ".dng", ".cr2", ".cr3", ".nef",
    ".arw", ".raf", ".orf", ".rw2", ".pef", ".srw",
})
# Destination formats that can't carry alpha — flatten to RGB before saving.
NO_ALPHA_FORMATS = frozenset({"jpg", "jpeg", "bmp"})


def open_upright(image_path: Path):
    """Open *image_path* decoded and turned upright by its EXIF orientation.

    Every tool works on the image as a viewer shows it: sizes, crop boxes and
    the written copies (which carry no EXIF) all use the upright pixels.
    """
    from PIL import Image

    from Imervue.image.orientation import exif_orientation, transpose_for
    with Image.open(image_path) as opened:
        opened.load()
        turned = transpose_for(opened, exif_orientation(opened))
        return turned if turned is not opened else opened.copy()


def load_rgba_array(image_path: Path):
    """Load *image_path* as an upright HxWx4 uint8 RGBA array."""
    import numpy as np
    with open_upright(image_path) as opened:
        return np.array(opened.convert("RGBA"))


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
