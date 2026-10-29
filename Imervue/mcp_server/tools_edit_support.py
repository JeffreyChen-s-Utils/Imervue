"""Validation and save helpers shared by the write-side MCP tool handlers.

Used by ``tools_edit`` (overlays, geometry) and the effect handlers in
``tools_edit_effects`` / ``tools_edit_grading``: destination and colour checks,
the output-size guard, alpha-aware saving and the shared "apply one effect and
save a copy" body.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from Imervue.mcp_server.tool_support import (
    NO_ALPHA_FORMATS,
    load_rgba_array,
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


def _validated_destination(destination: str) -> Path:
    """Return the destination Path, requiring its parent directory to exist."""
    dst = Path(destination)
    if not dst.parent.exists():
        raise ValueError(f"destination parent {dst.parent} does not exist")
    return dst


def _guard_output_pixels(width: int, height: int) -> None:
    """Reject absurd output geometry before allocating the buffer."""
    if width * height > _MAX_OUTPUT_PIXELS:
        raise ValueError(
            f"output {width}x{height} exceeds the "
            f"{_MAX_OUTPUT_PIXELS}-pixel limit",
        )


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
