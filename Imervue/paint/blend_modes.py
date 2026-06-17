"""Shared RGB blend-mode math for the paint engine.

Both the per-dab brush engine (:mod:`Imervue.paint.brush_engine`) and the
per-layer compositor (:mod:`Imervue.paint.compositing`) blend two ``[0, 1]``
RGB arrays with the same twelve Photoshop-style modes. The formula table lived
in both files as a byte-for-byte copy; keeping it here in one place stops the
two from silently drifting apart. ``brush_engine`` re-exports
:data:`BLEND_MODES` and ``compositing`` re-exports it as ``LAYER_BLEND_MODES``,
so existing importers of either name are unaffected.
"""
from __future__ import annotations

import numpy as np

BLEND_MODES = (
    "normal", "multiply", "screen", "overlay",
    "darken", "lighten",
    "color_dodge", "color_burn",
    "soft_light", "hard_light",
    "linear_burn", "linear_dodge",
)


def _d_curve(x: np.ndarray) -> np.ndarray:
    """Photoshop's D(x) used by soft-light: square-root for x>0.25 else
    a polynomial that joins smoothly."""
    return np.where(x <= 0.25, ((16.0 * x - 12.0) * x + 4.0) * x, np.sqrt(x))


def blend_rgb(bg: np.ndarray, fg: np.ndarray, mode: str) -> np.ndarray:
    """Per-pixel blend of two ``[0, 1]`` RGB arrays using *mode*."""
    if mode == "normal":
        return fg
    if mode == "multiply":
        return bg * fg
    if mode == "screen":
        return 1.0 - (1.0 - bg) * (1.0 - fg)
    if mode == "overlay":
        return np.where(bg <= 0.5, 2.0 * bg * fg, 1.0 - 2.0 * (1.0 - bg) * (1.0 - fg))
    if mode == "darken":
        return np.minimum(bg, fg)
    if mode == "lighten":
        return np.maximum(bg, fg)
    if mode == "color_dodge":
        return np.where(fg >= 1.0, 1.0, np.minimum(1.0, bg / np.maximum(1.0 - fg, 1e-6)))
    if mode == "color_burn":
        return np.where(
            fg <= 0.0, 0.0,
            1.0 - np.minimum(1.0, (1.0 - bg) / np.maximum(fg, 1e-6)),
        )
    if mode == "soft_light":
        return np.where(
            fg <= 0.5,
            bg - (1.0 - 2.0 * fg) * bg * (1.0 - bg),
            bg + (2.0 * fg - 1.0) * (_d_curve(bg) - bg),
        )
    if mode == "hard_light":
        return np.where(fg <= 0.5, 2.0 * bg * fg, 1.0 - 2.0 * (1.0 - bg) * (1.0 - fg))
    if mode == "linear_burn":
        return np.maximum(bg + fg - 1.0, 0.0)
    if mode == "linear_dodge":
        return np.minimum(bg + fg, 1.0)
    raise ValueError(f"unknown blend_mode {mode!r}")
