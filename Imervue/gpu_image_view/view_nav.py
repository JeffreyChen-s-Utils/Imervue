"""Deep-zoom view navigation helpers.

Pure-Python math extracted from ``GPUImageView`` so view-transform decisions
are unit-testable without an OpenGL context.
"""
from __future__ import annotations

ACTUAL_SIZE_ZOOM = 1.0


def toggle_zoom_target(
    current_zoom: float,
    fit_zoom: float,
    *,
    actual: float = ACTUAL_SIZE_ZOOM,
    eps: float = 1e-3,
) -> float:
    """Return the zoom to switch to on a fit ↔ 100% toggle.

    At (or very near) 100% the toggle returns the fit zoom; from any other
    level it returns 100%. This mirrors the double-click behaviour common to
    image viewers.
    """
    if abs(current_zoom - actual) < eps:
        return fit_zoom
    return actual


def stepped_zoom(current: float, factor: float, lo: float, hi: float) -> float:
    """Multiply *current* zoom by *factor*, clamped to ``[lo, hi]``.

    Shared by the wheel, keyboard and pinch zoom paths so they all honour the
    same limits.
    """
    return max(lo, min(hi, current * factor))


def zoom_about_point(
    offset: float,
    cursor: float,
    old_zoom: float,
    new_zoom: float,
) -> float:
    """Return the pan offset that keeps the image point under *cursor* fixed
    while the zoom changes from *old_zoom* to *new_zoom*.

    Works on a single axis; call once per axis. ``old_zoom`` of zero is guarded
    so a degenerate state can't divide by zero.
    """
    ratio = new_zoom / old_zoom if old_zoom else 1.0
    return cursor - (cursor - offset) * ratio
