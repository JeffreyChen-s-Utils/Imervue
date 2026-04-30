"""Export-time utilities — watermark, per-layer export, slice export.

Three small helpers the export pipeline reaches for:

* :func:`apply_watermark` — composite a watermark image at one of
  five canonical positions with configurable opacity + padding.
* :func:`export_layer` — write a single :class:`Layer`'s image as
  a standalone PNG via Pillow.
* :func:`slice_export` — slice the canvas into named rectangles
  and write each slice as a separate file. Useful for sprite-sheet
  workflows or web-asset generation.

Pure-numpy + Pillow; the dispatcher / menu layer wraps these with
the file-dialog UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

WATERMARK_POSITIONS = (
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "center",
)
DEFAULT_PADDING = 16


@dataclass(frozen=True)
class Slice:
    """One named rectangular slice for :func:`slice_export`."""

    name: str
    x: int
    y: int
    w: int
    h: int

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("slice name must be non-empty")
        if int(self.w) <= 0 or int(self.h) <= 0:
            raise ValueError(
                f"slice {self.name!r} must have positive size, "
                f"got {self.w}×{self.h}",
            )


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------


def apply_watermark(
    image: np.ndarray,
    watermark: np.ndarray,
    *,
    position: str = "bottom-right",
    opacity: float = 1.0,
    padding: int = DEFAULT_PADDING,
) -> np.ndarray:
    """Composite ``watermark`` onto ``image`` at ``position``.

    Both images must be HxWx4 uint8 RGBA. The watermark must fit
    inside the image after subtracting padding. ``opacity`` in
    ``[0, 1]`` scales the watermark's alpha at composite time;
    ``opacity = 0`` short-circuits to a copy of the input.

    Returns a fresh image — the inputs are not mutated.
    """
    _check_rgba(image, name="image")
    _check_rgba(watermark, name="watermark")
    if position not in WATERMARK_POSITIONS:
        raise ValueError(
            f"unknown watermark position {position!r}; "
            f"expected one of {WATERMARK_POSITIONS}",
        )
    opacity = max(0.0, min(1.0, float(opacity)))
    padding = max(0, int(padding))
    if opacity == 0.0:
        return image.copy()

    h, w = image.shape[:2]
    wh, ww = watermark.shape[:2]
    if wh > h - 2 * padding or ww > w - 2 * padding:
        raise ValueError(
            f"watermark ({wh}×{ww}) does not fit in image "
            f"({h}×{w}) with padding {padding}",
        )

    if position == "top-left":
        x0, y0 = padding, padding
    elif position == "top-right":
        x0, y0 = w - ww - padding, padding
    elif position == "bottom-left":
        x0, y0 = padding, h - wh - padding
    elif position == "bottom-right":
        x0, y0 = w - ww - padding, h - wh - padding
    else:   # center
        x0 = (w - ww) // 2
        y0 = (h - wh) // 2

    out = image.copy()
    _alpha_composite(
        out, watermark, x0, y0, opacity=opacity,
    )
    return out


def _alpha_composite(
    dst: np.ndarray, src: np.ndarray, x0: int, y0: int, *, opacity: float,
) -> None:
    """Straight-alpha porter-duff over: ``src`` painted onto ``dst``
    at ``(x0, y0)``, ``opacity`` scales src alpha. Mutates ``dst``."""
    sh, sw = src.shape[:2]
    src_f = src.astype(np.float32) / 255.0
    dst_f = dst[y0:y0 + sh, x0:x0 + sw].astype(np.float32) / 255.0
    src_a = src_f[..., 3:4] * float(opacity)
    dst_a = dst_f[..., 3:4]
    out_a = src_a + dst_a * (1.0 - src_a)
    safe_a = np.where(out_a < 1e-6, 1.0, out_a)
    out_rgb = (
        src_f[..., :3] * src_a + dst_f[..., :3] * dst_a * (1.0 - src_a)
    ) / safe_a
    dst[y0:y0 + sh, x0:x0 + sw, :3] = np.clip(
        out_rgb * 255.0, 0.0, 255.0,
    ).astype(np.uint8)
    dst[y0:y0 + sh, x0:x0 + sw, 3] = np.clip(
        out_a[..., 0] * 255.0, 0.0, 255.0,
    ).astype(np.uint8)


# ---------------------------------------------------------------------------
# Per-layer export
# ---------------------------------------------------------------------------


def export_layer(layer_image: np.ndarray, path: str | Path) -> None:
    """Write a single layer image as PNG.

    The layer is saved as-is — no flattening, no compositing. Useful
    for "extract this layer for use elsewhere" workflows.
    """
    _check_rgba(layer_image, name="layer_image")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(layer_image, mode="RGBA").save(str(target), format="PNG")


# ---------------------------------------------------------------------------
# Slice export
# ---------------------------------------------------------------------------


def slice_export(
    image: np.ndarray,
    slices: list[Slice],
    output_dir: str | Path,
    *,
    file_format: str = "PNG",
) -> list[Path]:
    """Cut ``image`` into the supplied named rectangles and write each
    one to ``output_dir`` / ``{name}.{ext}``.

    Returns the list of paths actually written. Slices that fall
    entirely outside the canvas are skipped silently. Slices that
    overlap the canvas edge are clipped to the visible region rather
    than raising — partial export is still useful.
    """
    _check_rgba(image, name="image")
    if not slices:
        return []
    fmt = str(file_format).upper()
    if fmt not in ("PNG", "WEBP", "JPEG", "BMP"):
        raise ValueError(
            f"unsupported file_format {file_format!r}; "
            f"expected one of PNG / WEBP / JPEG / BMP",
        )
    extension = ".jpg" if fmt == "JPEG" else f".{fmt.lower()}"
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    h, w = image.shape[:2]
    written: list[Path] = []
    for slice_def in slices:
        x0 = max(0, int(slice_def.x))
        y0 = max(0, int(slice_def.y))
        x1 = min(w, int(slice_def.x) + int(slice_def.w))
        y1 = min(h, int(slice_def.y) + int(slice_def.h))
        if x1 <= x0 or y1 <= y0:
            continue
        section = image[y0:y1, x0:x1]
        # JPEG can't store an alpha channel — drop it for that format.
        if fmt == "JPEG":
            pil = Image.fromarray(section, mode="RGBA").convert("RGB")
        else:
            pil = Image.fromarray(section, mode="RGBA")
        path = target_dir / f"{_safe_filename(slice_def.name)}{extension}"
        pil.save(str(path), format=fmt)
        written.append(path)
    return written


def _safe_filename(name: str) -> str:
    """Strip path separators + control chars so a slice name can't
    escape the output directory."""
    cleaned = (
        str(name)
        .replace("/", "_")
        .replace("\\", "_")
        .replace("..", "_")
        .strip()
    )
    return cleaned or "slice"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _check_rgba(image: np.ndarray, *, name: str) -> None:
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"{name} must be HxWx4 uint8 RGBA, got "
            f"{image.shape} {image.dtype}",
        )
