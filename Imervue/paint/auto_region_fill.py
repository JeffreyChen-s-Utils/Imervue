"""One-shot "fill every enclosed region" — MediBang's bucket-all.

Pure-numpy line-art flat-fill: take a reference (line-art) buffer,
threshold it into "ink" vs "paper", connected-component label the
paper pixels with 4-connectivity, drop tiny anti-alias dust and the
single big border-touching blob (which is the empty exterior), then
paint the surviving blobs into the destination canvas with the
foreground colour.

This is the traditional flat-painter shortcut for inked manga pages:
one click and every closed cell on the line-art layer is filled at
once, then the user re-paints individual cells with proper colours.

The connected-component pass uses an iterative scanline flood that
matches :func:`Imervue.paint.fill._contiguous_region` so behaviour
is identical to the per-click bucket — same gap-bridging discipline,
same neighbour walk. The labelled grid is computed in a single sweep
without scipy as a dependency.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


THRESHOLD_MIN = 0
THRESHOLD_MAX = 255
DEFAULT_THRESHOLD = 128
DEFAULT_MIN_AREA = 4


@dataclass(frozen=True)
class AutoFillResult:
    """Damage rect + region tally for ``auto_region_fill``.

    ``regions_filled`` is the number of distinct closed regions the
    pass painted — useful for telemetry and as a friendly status-bar
    message ("filled 14 regions").
    """

    x: int
    y: int
    w: int
    h: int
    pixels_filled: int
    regions_filled: int

    @property
    def is_empty(self) -> bool:
        return self.pixels_filled <= 0


def auto_region_fill(
    canvas: np.ndarray,
    line_art: np.ndarray,
    color: tuple[int, int, int],
    *,
    threshold: int = DEFAULT_THRESHOLD,
    min_area: int = DEFAULT_MIN_AREA,
    drop_border_regions: bool = True,
    selection: np.ndarray | None = None,
) -> AutoFillResult:
    """Fill every closed region in ``line_art`` with ``color`` on ``canvas``.

    ``line_art`` and ``canvas`` must share the same H/W; both are
    HxWx4 uint8 RGBA. The line mask is the set of pixels whose mean
    RGB is below ``threshold`` *and* whose alpha is non-zero — so a
    transparent line-art layer (untouched ink) leaves every pixel as
    "paper" and the entire canvas counts as one big region. Pixels
    on the canvas border that fall in the same blob as the exterior
    are skipped when ``drop_border_regions`` is True (the default).
    Blobs smaller than ``min_area`` pixels are also skipped to keep
    AA halos out of the result.
    """
    _check_rgba("canvas", canvas)
    _check_rgba("line_art", line_art)
    if line_art.shape[:2] != canvas.shape[:2]:
        raise ValueError(
            f"line_art shape {line_art.shape[:2]} does not match "
            f"canvas {canvas.shape[:2]}",
        )
    threshold = max(THRESHOLD_MIN, min(THRESHOLD_MAX, int(threshold)))
    if int(min_area) < 0:
        raise ValueError(f"min_area must be >= 0, got {min_area}")
    h, w = canvas.shape[:2]
    if selection is not None and selection.shape != (h, w):
        raise ValueError(
            f"selection mask shape {selection.shape} does not match "
            f"canvas {(h, w)}",
        )

    # Mean RGB darker than ``threshold`` *and* opaque counts as ink.
    rgb_mean = line_art[..., :3].mean(axis=-1)
    alpha = line_art[..., 3]
    ink = (rgb_mean < threshold) & (alpha > 0)
    paper = ~ink
    if selection is not None:
        paper = paper & selection
    if not paper.any():
        return AutoFillResult(0, 0, 0, 0, 0, 0)

    labels = _label_connected(paper)
    fill_mask = _select_fillable_regions(
        labels, paper, drop_border_regions, int(min_area),
    )

    pixels_filled = int(fill_mask.sum())
    if pixels_filled == 0:
        return AutoFillResult(0, 0, 0, 0, 0, 0)

    canvas[fill_mask, 0] = int(color[0])
    canvas[fill_mask, 1] = int(color[1])
    canvas[fill_mask, 2] = int(color[2])
    canvas[fill_mask, 3] = 255

    ys, xs = np.nonzero(fill_mask)
    region_count = int(len(np.unique(labels[fill_mask])))
    return AutoFillResult(
        int(xs.min()), int(ys.min()),
        int(xs.max() - xs.min() + 1),
        int(ys.max() - ys.min() + 1),
        pixels_filled, region_count,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _label_connected(mask: np.ndarray) -> np.ndarray:
    """Return an int32 label grid: 0 = not in mask, 1..N = component id.

    Uses the same scanline flood as the bucket tool, iterated over
    every unvisited pixel. Linear in the total mask area and bounded
    in memory by one HxW int32 grid plus the scanline stack.
    """
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    next_label = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x] != 0:
                continue
            next_label += 1
            _flood_label(mask, labels, x, y, next_label)
    return labels


def _flood_label(
    mask: np.ndarray, labels: np.ndarray, sx: int, sy: int, label: int,
) -> None:
    """Scanline flood that stamps ``label`` into every reachable cell.

    Mirrors ``fill._contiguous_region`` with one mutation: we write
    a label int into the labels grid instead of a boolean mask, and
    we read the visited flag off `labels != 0` instead of a parallel
    array. Same neighbour walk so behaviour is identical.
    """
    h, w = mask.shape
    stack: list[tuple[int, int]] = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        if labels[y, x] != 0 or not mask[y, x]:
            continue
        x_left = x
        while (
            x_left > 0
            and mask[y, x_left - 1]
            and labels[y, x_left - 1] == 0
        ):
            x_left -= 1
        x_right = x
        while (
            x_right < w - 1
            and mask[y, x_right + 1]
            and labels[y, x_right + 1] == 0
        ):
            x_right += 1
        labels[y, x_left : x_right + 1] = label
        for ny in (y - 1, y + 1):
            if not (0 <= ny < h):
                continue
            row_mask = mask[ny, x_left : x_right + 1]
            row_open = row_mask & (labels[ny, x_left : x_right + 1] == 0)
            i = 0
            row_len = row_open.shape[0]
            while i < row_len:
                if row_open[i]:
                    stack.append((x_left + i, ny))
                    while i < row_len and row_open[i]:
                        i += 1
                else:
                    i += 1


def _select_fillable_regions(
    labels: np.ndarray,
    paper: np.ndarray,
    drop_border_regions: bool,
    min_area: int,
) -> np.ndarray:
    """Reduce a label grid to a boolean mask of regions to paint."""
    if labels.max() == 0:
        return np.zeros_like(paper, dtype=bool)

    # Bin-count gives one entry per label including background (0).
    counts = np.bincount(labels.ravel())
    border_labels: set[int] = set()
    if drop_border_regions:
        border_labels.update(np.unique(labels[0, :]).tolist())
        border_labels.update(np.unique(labels[-1, :]).tolist())
        border_labels.update(np.unique(labels[:, 0]).tolist())
        border_labels.update(np.unique(labels[:, -1]).tolist())
        border_labels.discard(0)

    keep = np.zeros_like(paper, dtype=bool)
    for label_id in range(1, len(counts)):
        if counts[label_id] < min_area:
            continue
        if label_id in border_labels:
            continue
        keep |= labels == label_id
    return keep


def _check_rgba(name: str, arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"{name} must be HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
        )
