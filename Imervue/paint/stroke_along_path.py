"""Run a brush stroke along a Bezier path.

Given a :class:`Imervue.paint.bezier_path.BezierPath` and the user's
brush settings, walk the path at a configurable spacing and stamp
the brush at each step. The result is the same look the user gets
from a freehand stroke — same kernel, same pressure dynamics — but
following the path exactly.

Pure-numpy / Qt-free. The interactive pen-tool wiring lives in
:mod:`tool_dispatcher` (Phase 20d will hook it up); this module
owns the verb that turns a finished path into pixels.
"""
from __future__ import annotations

import math

import numpy as np

from Imervue.paint.bezier_path import BezierPath, sample_path
from Imervue.paint.brush_engine import (
    BrushStrokeOptions,
    apply_dab,
    round_brush_kernel,
    spacing_from_brush,
)
from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.damage import DamageRect, from_dab_result

DEFAULT_SAMPLES_PER_SEGMENT = 32


def stroke_along_path(
    canvas: np.ndarray,
    path: BezierPath,
    options: BrushStrokeOptions,
    *,
    samples_per_segment: int = DEFAULT_SAMPLES_PER_SEGMENT,
) -> DamageRect:
    """Paint ``options.color`` along ``path`` onto ``canvas`` in place.

    ``samples_per_segment`` controls how finely the path is
    rasterised before the brush spacing kicks in — finer is more
    accurate on tight curves but quadratic-ish in cost. The default
    is ample for the screen sizes paint apps run at.

    Returns the union damage rectangle so the canvas widget can
    schedule a partial texture upload.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    samples = sample_path(path, samples_per_segment=samples_per_segment)
    if len(samples) < 2:
        return EMPTY_DAMAGE
    spacing = options.spacing if options.spacing is not None else (
        spacing_from_brush(options.size, options.hardness)
    )
    spacing = max(1.0, float(spacing))
    kernel = round_brush_kernel(options.size, options.hardness)
    color_rgb = (
        int(options.color[0]),
        int(options.color[1]),
        int(options.color[2]),
    )

    damage = EMPTY_DAMAGE
    last_x, last_y = samples[0]
    # Stamp the first sample exactly once.
    damage = damage.union(from_dab_result(apply_dab(
        canvas, last_x, last_y, kernel, color_rgb,
        opacity=options.opacity,
        blend_mode=options.blend_mode,
        selection=options.selection,
    )))
    accumulated = 0.0
    for sx, sy in samples[1:]:
        dx = sx - last_x
        dy = sy - last_y
        seg_length = math.hypot(dx, dy)
        if seg_length <= 0.0:
            continue
        accumulated += seg_length
        # Step along the segment in spacing-sized increments. The
        # fractional remainder rolls over to the next segment so the
        # brush spacing stays uniform across joins.
        while accumulated >= spacing:
            t = 1.0 - (accumulated - spacing) / seg_length
            stamp_x = last_x + dx * t
            stamp_y = last_y + dy * t
            damage = damage.union(from_dab_result(apply_dab(
                canvas, stamp_x, stamp_y, kernel, color_rgb,
                opacity=options.opacity,
                blend_mode=options.blend_mode,
                selection=options.selection,
            )))
            accumulated -= spacing
        last_x, last_y = sx, sy
    return damage
