"""Compose puppet animation frames into a single spritesheet image.

The recorder already exports motion to GIF/MP4/WebM; a spritesheet packs the
frames into one grid PNG for game engines / CSS sprite animation. The grid
choice and tiling are pure numpy (Qt/GL-free) so they are unit-testable; saving
is a thin PIL write.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

DEFAULT_MAX_COLS = 8


def grid_dimensions(frame_count: int, max_cols: int = DEFAULT_MAX_COLS) -> tuple[int, int]:
    """Return ``(cols, rows)`` for *frame_count* frames, capped at *max_cols*.

    A near-square-ish grid that never exceeds ``max_cols`` columns. Zero or
    negative counts yield ``(0, 0)``; ``max_cols`` below 1 is treated as 1.
    """
    if frame_count <= 0:
        return 0, 0
    cols = min(frame_count, max(1, max_cols))
    rows = -(-frame_count // cols)  # ceil division
    return cols, rows


def compose_spritesheet(frames: list[np.ndarray], cols: int) -> np.ndarray:
    """Tile equally-sized *frames* row-major into a ``(rows*H, cols*W, C)`` sheet.

    Frames must be a non-empty list of identically-shaped HxWxC uint8 arrays.
    Cells past the last frame stay transparent/black. Raises ``ValueError`` on
    an empty list, a non-positive ``cols``, or mismatched frame shapes.
    """
    if not frames:
        raise ValueError("compose_spritesheet needs at least one frame")
    if cols <= 0:
        raise ValueError(f"cols must be positive, got {cols}")
    shape = frames[0].shape
    if any(f.shape != shape for f in frames):
        raise ValueError("all frames must share the same shape")
    height, width = shape[0], shape[1]
    channels = shape[2] if len(shape) == 3 else 1
    rows = -(-len(frames) // cols)
    sheet = np.zeros((rows * height, cols * width, channels), dtype=frames[0].dtype)
    for index, frame in enumerate(frames):
        row, col = divmod(index, cols)
        block = frame if frame.ndim == 3 else frame[:, :, None]
        sheet[row * height:(row + 1) * height, col * width:(col + 1) * width] = block
    return sheet


def save_spritesheet(
    frames: list[np.ndarray],
    path: str | Path,
    max_cols: int = DEFAULT_MAX_COLS,
) -> tuple[int, int]:
    """Compose *frames* and write the sheet as a PNG; returns ``(cols, rows)``."""
    from PIL import Image
    cols, rows = grid_dimensions(len(frames), max_cols)
    sheet = compose_spritesheet(frames, cols)
    if sheet.shape[2] == 1:
        sheet = sheet[:, :, 0]
    Image.fromarray(sheet).save(str(path))
    return cols, rows
