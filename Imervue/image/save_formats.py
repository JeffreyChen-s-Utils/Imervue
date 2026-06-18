"""Shared image output-format metadata and saving.

The export and batch-convert dialogs previously each carried their own format
tables and ``Image.save`` calls. This module is the single source of truth so
adding a format (e.g. HEIC / AVIF) touches one place.

HEIC/AVIF output rides on the optional ``pillow-heif`` backend: it is offered
only when the backend is installed (:func:`available_formats`) and the save
registers the opener on demand. A single ``register_heif_opener`` covers both
HEIF and AVIF; the only Pillow-side wrinkle is that the ``.heic`` container is
written with the ``HEIF`` plugin id, hence :func:`pil_format`.
"""
from __future__ import annotations

from typing import BinaryIO

from PIL import Image

from Imervue.image.heif_support import ensure_heif_opener
from Imervue.image.jxl_support import ensure_jxl_opener

# Display name → file extension.
FORMAT_EXTENSIONS: dict[str, str] = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WebP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "HEIC": ".heic",
    "AVIF": ".avif",
    "JXL": ".jxl",
}
# Formats whose ``save`` honours a 0-100 quality parameter.
QUALITY_FORMATS: frozenset[str] = frozenset({"JPEG", "WebP", "HEIC", "AVIF", "JXL"})

_BASE_FORMATS: tuple[str, ...] = ("PNG", "JPEG", "WebP", "BMP", "TIFF")
# Ordered so the menu shows HEIC before AVIF deterministically.
_HEIF_FORMATS_ORDER: tuple[str, ...] = ("HEIC", "AVIF")
_HEIF_FORMATS: frozenset[str] = frozenset(_HEIF_FORMATS_ORDER)
# Formats that cannot carry an alpha channel.
_NO_ALPHA_FORMATS: frozenset[str] = frozenset({"JPEG", "BMP"})
# Display name → Pillow format id (only HEIC differs).
_PIL_FORMAT_OVERRIDE: dict[str, str] = {"HEIC": "HEIF"}


def available_formats() -> list[str]:
    """Output formats offered to the user; HEIC/AVIF only if the backend exists."""
    formats = list(_BASE_FORMATS)
    if ensure_heif_opener():
        formats.extend(_HEIF_FORMATS_ORDER)
    if ensure_jxl_opener():
        formats.append("JXL")
    return formats


def pil_format(format_name: str) -> str:
    """Return the Pillow format id for a display format name."""
    return _PIL_FORMAT_OVERRIDE.get(format_name, format_name)


def prepare_for_format(img: Image.Image, format_name: str) -> Image.Image:
    """Convert ``img`` to a mode the target format can store."""
    if format_name in _NO_ALPHA_FORMATS and img.mode in ("RGBA", "P", "LA"):
        return img.convert("RGB")
    if img.mode not in ("RGB", "RGBA", "L"):
        return img.convert("RGBA")
    return img


def save_image(
    img: Image.Image,
    fp: str | BinaryIO,
    format_name: str,
    quality: int | None = None,
    extra: dict | None = None,
) -> None:
    """Save ``img`` as ``format_name`` to a path or file object.

    ``extra`` carries format-agnostic save options (e.g. ``dpi``) merged after
    the quality handling. Registers the HEIF/AVIF backend on demand and raises
    ``ValueError`` when a HEIC/AVIF save is requested without ``pillow-heif``
    installed, so callers can report it at the boundary.
    """
    if format_name in _HEIF_FORMATS and not ensure_heif_opener():
        raise ValueError(
            f"{format_name} output requires the pillow-heif package.",
        )
    if format_name == "JXL" and not ensure_jxl_opener():
        raise ValueError("JXL output requires the pillow-jxl-plugin package.")
    prepared = prepare_for_format(img, format_name)
    kwargs: dict = {}
    if quality is not None and format_name in QUALITY_FORMATS:
        kwargs["quality"] = int(quality)
    if extra:
        kwargs.update(extra)
    prepared.save(fp, format=pil_format(format_name), **kwargs)
