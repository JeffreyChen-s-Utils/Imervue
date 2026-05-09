"""Pure-numpy flood fill for the paint bucket tool.

Two modes:

* contiguous (default) — only fill pixels reachable from the seed
  through 4-connected steps that all stay within the colour-tolerance
  band. The classic paint-bucket behaviour.
* global — fill every pixel that matches the seed within tolerance,
  regardless of connectivity. MediBang's "all matching pixels" mode.

Tolerance is the maximum per-channel absolute RGB difference allowed
versus the seed. ``tolerance=0`` requires an exact match; ``tolerance=255``
matches everything. Alpha on the *write* canvas is always set to 255
on filled pixels (otherwise the bucket would deposit translucent paint
that's a foot-gun to debug).

Two MediBang-flavour extensions ride on top:

* ``reference_image`` — when supplied, connectivity / tolerance are
  evaluated against this *other* HxWx3 or HxWx4 uint8 buffer instead
  of ``canvas``. Use case: the user paints on an empty colour layer
  while the bucket reads boundaries from a separate line-art layer.
  The compare uses every channel of the reference (RGB + alpha if
  present) so a transparent-vs-opaque ink boundary is a hard wall
  regardless of the line colour.
* ``expand`` — after the contiguous / global mask is computed, dilate
  it by N pixels (4-connectivity) before painting. Bridges the
  anti-aliased halo around lineart so colour creeps under the ink
  edge — MediBang's "Close Gap" / "縮放" slider.

The contiguous flood uses iterative 4-connectivity dilation against
a precomputed candidate mask. This is vectorised so it stays fast on
large canvases without scipy as a dependency. Worst-case iterations
are bounded by the canvas diameter; typical fills converge in tens of
passes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FillResult:
    """Damage rect describing which pixels the fill changed."""

    x: int
    y: int
    w: int
    h: int
    pixels_filled: int

    @property
    def is_empty(self) -> bool:
        return self.pixels_filled <= 0


MAX_EXPAND = 32
MAX_GAP_CLOSE = 16


def flood_fill(
    canvas: np.ndarray,
    seed_x: int,
    seed_y: int,
    color: tuple[int, int, int],
    *,
    tolerance: int = 32,
    contiguous: bool = True,
    selection: np.ndarray | None = None,
    reference_image: np.ndarray | None = None,
    expand: int = 0,
    gap_close: int = 0,
) -> FillResult:
    """Fill the region around ``(seed_x, seed_y)`` with ``color``.

    If ``selection`` is provided (HxW bool mask), the fill is clipped
    to the selection — pixels outside it are never modified, even when
    they fall inside the colour-tolerance band.

    If ``reference_image`` is provided (HxWx3 or HxWx4 uint8), the seed
    pixel and per-pixel tolerance comparison use that buffer instead of
    ``canvas``. The write target is always ``canvas``. The reference is
    compared on all of its channels — including alpha when present —
    so an opaque/transparent boundary in the reference acts as a hard
    wall even if the foreground colour matches across it.

    ``expand`` (0..``MAX_EXPAND``) dilates the resulting fill mask by
    that many 4-connected pixels before painting, so the colour creeps
    under the anti-aliased halo of the reference lineart. ``expand=0``
    is a no-op.

    ``gap_close`` (0..``MAX_GAP_CLOSE``) is MediBang's "Color Drop"
    feature — temporarily dilate the ink mask by ``gap_close`` 4-
    connected pixels before flooding so small gaps in the lineart
    (broken pen strokes, AA leaks) bridge for the duration of the
    fill. Closes gaps up to ``2 * gap_close`` pixels wide; bigger
    gaps stay open. The original lineart pixels are never touched —
    the dilation only affects which cells the flood sees as
    boundaries. Trade-off: legitimate corridors thinner than
    ``2 * gap_close`` also vanish for this fill, so the user picks
    the radius for the largest gap they want to bridge.
    ``gap_close=0`` is a no-op.
    """
    _check_canvas(canvas)
    h, w = canvas.shape[:2]
    sx, sy = int(round(seed_x)), int(round(seed_y))
    if not (0 <= sx < w and 0 <= sy < h):
        return FillResult(0, 0, 0, 0, 0)
    if not _seed_in_selection(selection, (h, w), sx, sy):
        return FillResult(0, 0, 0, 0, 0)

    tolerance = max(0, min(255, int(tolerance)))
    expand_px = _validate_expand(expand)
    gap_close_px = _validate_gap_close(gap_close)

    candidates = _build_candidate_mask(
        canvas, reference_image, (h, w), sx, sy,
        tolerance=tolerance, gap_close_px=gap_close_px,
    )
    if selection is not None:
        candidates = candidates & selection

    mask = _contiguous_region(candidates, sx, sy) if contiguous else candidates
    mask = _apply_expand(mask, expand_px, selection)

    pixels_filled = int(mask.sum())
    if pixels_filled == 0:
        return FillResult(0, 0, 0, 0, 0)

    canvas[mask, 0] = int(color[0])
    canvas[mask, 1] = int(color[1])
    canvas[mask, 2] = int(color[2])
    canvas[mask, 3] = 255

    ys, xs = np.nonzero(mask)
    return FillResult(
        int(xs.min()), int(ys.min()),
        int(xs.max() - xs.min() + 1),
        int(ys.max() - ys.min() + 1),
        pixels_filled,
    )


def _seed_in_selection(
    selection: np.ndarray | None,
    shape: tuple[int, int],
    sx: int,
    sy: int,
) -> bool:
    """Check that the seed lies inside the selection mask if one is
    supplied. Raises if the mask shape doesn't match the canvas."""
    if selection is None:
        return True
    if selection.shape != shape:
        raise ValueError(
            f"selection mask shape {selection.shape} does not match "
            f"canvas {shape}",
        )
    return bool(selection[sy, sx])


def _build_candidate_mask(
    canvas: np.ndarray,
    reference_image: np.ndarray | None,
    shape: tuple[int, int],
    sx: int,
    sy: int,
    *,
    tolerance: int,
    gap_close_px: int,
) -> np.ndarray:
    """Build the per-pixel "may be filled" mask: tolerance match against
    the seed, alpha-boundary gate, plus optional gap-close ink dilation.

    The alpha gate fires only when there is no separate reference
    image — the eraser preserves RGB on alpha=0 pixels, so without it
    a flood seeded on visible paint would bleed across erased pixels
    that happen to share the seed's RGB. With a reference image, that
    buffer's own alpha already participates in the tolerance diff, so
    re-gating would double-count the boundary.
    """
    sample = _resolve_sample_buffer(reference_image, canvas, shape)
    seed = sample[sy, sx].astype(np.int16)
    diff = np.abs(sample.astype(np.int16) - seed[None, None, :])
    candidates = diff.max(axis=-1) <= tolerance
    if reference_image is None:
        pixel_visible = canvas[..., 3] > 0
        candidates &= pixel_visible if int(canvas[sy, sx, 3]) > 0 else ~pixel_visible
    if gap_close_px > 0:
        # Pure dilation of the ink (not-candidates) by ``gap_close_px``
        # bridges broken-line gaps up to ``2 * gap_close_px`` wide for
        # the duration of this flood. Closing-then-erode would leave
        # 1-px gaps in 1-px lines unbridged because the eroded bridge
        # has no surviving neighbour, so we keep pure dilation to match
        # MediBang's "Close gap" slider.
        from Imervue.paint.selection_ops import expand as dilate
        ink_thickened = dilate(~candidates, gap_close_px)
        candidates = ~ink_thickened
    return candidates


def _apply_expand(
    mask: np.ndarray,
    expand_px: int,
    selection: np.ndarray | None,
) -> np.ndarray:
    """Optionally dilate the fill mask by ``expand_px`` and re-clip to
    the selection. ``expand_px == 0`` returns the mask unchanged."""
    if expand_px <= 0 or not mask.any():
        return mask
    from Imervue.paint.selection_ops import expand as expand_mask
    grown = expand_mask(mask, expand_px)
    if selection is not None:
        grown = grown & selection
    return grown


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _contiguous_region(candidates: np.ndarray, sx: int, sy: int) -> np.ndarray:
    """Scanline flood fill from the seed, clipped by ``candidates``.

    The previous "iterative whole-canvas dilation" approach allocated
    five HxW arrays per iteration and scaled with the diameter of the
    flood region — pathological on large canvases (a 4K paint hung
    the UI for several seconds). This scanline version walks a stack
    of horizontal runs, marking them on a single output mask, and
    expands above / below by checking the edges of each run. Memory
    use is bounded; runtime is linear in the number of pixels in the
    region rather than ``H * W * diameter``.
    """
    h, w = candidates.shape
    if not candidates[sy, sx]:
        return np.zeros_like(candidates)

    mask = np.zeros_like(candidates)
    # Stack of starting points; each pop runs a full horizontal scan.
    stack: list[tuple[int, int]] = [(int(sx), int(sy))]
    while stack:
        x, y = stack.pop()
        if not (0 <= y < h):
            continue
        if mask[y, x] or not candidates[y, x]:
            continue
        # Walk left along this row until we hit a non-candidate cell
        # or a previously-visited one.
        x_left = x
        while x_left > 0 and candidates[y, x_left - 1] and not mask[y, x_left - 1]:
            x_left -= 1
        # And right from the seed.
        x_right = x
        while (
            x_right < w - 1
            and candidates[y, x_right + 1]
            and not mask[y, x_right + 1]
        ):
            x_right += 1
        # Mark the run.
        mask[y, x_left : x_right + 1] = True
        # Walk the row above and below; any candidate-but-unvisited
        # pixel on those rows seeds a new run.
        for ny in (y - 1, y + 1):
            if not (0 <= ny < h):
                continue
            row_open = candidates[ny, x_left : x_right + 1] & ~mask[ny, x_left : x_right + 1]
            # Find the start of every contiguous "True" run on the
            # neighbour row by walking the boolean array; push only
            # the leftmost cell of each run so we don't redo work.
            i = 0
            row_len = row_open.shape[0]
            while i < row_len:
                if row_open[i]:
                    stack.append((x_left + i, ny))
                    while i < row_len and row_open[i]:
                        i += 1
                else:
                    i += 1
    return mask


def _check_canvas(canvas: np.ndarray) -> None:
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"flood_fill expects HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )


def _resolve_sample_buffer(
    reference_image: np.ndarray | None,
    canvas: np.ndarray,
    shape: tuple[int, int],
) -> np.ndarray:
    """Return the buffer to test connectivity / tolerance against.

    Falls back to the canvas's RGB channels when no reference is given.
    A reference must match the canvas height / width and be uint8 with
    3 or 4 channels; the channel count is preserved so an opaque/
    transparent boundary in the reference participates in the diff.
    """
    if reference_image is None:
        return canvas[..., :3]
    if reference_image.ndim != 3 or reference_image.dtype != np.uint8:
        raise ValueError(
            f"reference_image must be HxWx3/4 uint8, got "
            f"{reference_image.shape} {reference_image.dtype}",
        )
    if reference_image.shape[:2] != shape:
        raise ValueError(
            f"reference_image shape {reference_image.shape[:2]} does not "
            f"match canvas {shape}",
        )
    if reference_image.shape[2] not in (3, 4):
        raise ValueError(
            f"reference_image must have 3 or 4 channels, got "
            f"{reference_image.shape[2]}",
        )
    return reference_image


def _validate_expand(expand: int) -> int:
    """Clamp / reject ``expand`` to the documented [0, MAX_EXPAND] range."""
    try:
        value = int(expand)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expand must be an integer, got {expand!r}") from exc
    if value < 0:
        raise ValueError(f"expand must be >= 0, got {value}")
    if value > MAX_EXPAND:
        raise ValueError(f"expand must be <= {MAX_EXPAND}, got {value}")
    return value


def _validate_gap_close(gap_close: int) -> int:
    """Clamp / reject ``gap_close`` to ``[0, MAX_GAP_CLOSE]``."""
    try:
        value = int(gap_close)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"gap_close must be an integer, got {gap_close!r}",
        ) from exc
    if value < 0:
        raise ValueError(f"gap_close must be >= 0, got {value}")
    if value > MAX_GAP_CLOSE:
        raise ValueError(f"gap_close must be <= {MAX_GAP_CLOSE}, got {value}")
    return value
