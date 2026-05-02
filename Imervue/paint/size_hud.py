"""Brush-size HUD overlay.

When the user changes brush size via the bracket keys or a slider,
a brief on-canvas indicator shows the new radius as a translucent
ring at the canvas centre. The ring fades out after a configurable
duration so it doesn't get in the way of the next stroke.

This module owns the pure-numpy renderer + the timing state machine.
The Qt widget (canvas) hooks into the state via :meth:`bump`,
:meth:`alpha_at`, and :func:`render_size_hud`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_FADE_DURATION_S = 0.8
DEFAULT_RING_THICKNESS_PX = 2
HUD_RING_COLOR = (255, 255, 255, 230)
HUD_SHADOW_COLOR = (0, 0, 0, 180)


@dataclass
class SizeHudState:
    """Tracks when the size HUD should fade in / fade out.

    Call :meth:`bump` whenever the brush size changes; the HUD then
    starts at full alpha and decays linearly over ``fade_duration_s``.
    The canvas widget polls :meth:`alpha_at` once per repaint to
    decide whether to paint anything.
    """

    last_change_at: float | None = None
    last_size: int = 0
    fade_duration_s: float = DEFAULT_FADE_DURATION_S

    def bump(self, *, size: int, now: float) -> None:
        """Record a size change. ``now`` is a monotonic timestamp."""
        if size <= 0:
            raise ValueError(f"size must be positive, got {size!r}")
        if self.fade_duration_s <= 0:
            raise ValueError(
                f"fade_duration_s must be > 0, got {self.fade_duration_s!r}",
            )
        self.last_change_at = float(now)
        self.last_size = int(size)

    def alpha_at(self, now: float) -> float:
        """Return the HUD's current alpha in [0, 1]; 0 means hide it."""
        if self.last_change_at is None:
            return 0.0
        elapsed = float(now) - self.last_change_at
        if elapsed <= 0:
            return 1.0
        if elapsed >= self.fade_duration_s:
            return 0.0
        return 1.0 - (elapsed / self.fade_duration_s)


def render_size_hud(
    canvas_size: tuple[int, int],
    centre: tuple[float, float],
    radius: float,
    *,
    alpha: float,
    thickness: int = DEFAULT_RING_THICKNESS_PX,
) -> np.ndarray:
    """Render the size-HUD ring as an HxWx4 RGBA overlay buffer.

    Two concentric outline rings — a black shadow underneath and a
    white foreground on top — give the indicator a readable look
    against any canvas content. Returned as a fresh buffer; the
    caller blits it on top of the layer composite.
    """
    h, w = canvas_size
    if h <= 0 or w <= 0:
        raise ValueError(
            f"canvas_size must be positive, got {canvas_size!r}",
        )
    if radius <= 0:
        raise ValueError(f"radius must be > 0, got {radius!r}")
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha!r}")
    if thickness < 1:
        raise ValueError(f"thickness must be >= 1, got {thickness!r}")
    out = np.zeros((h, w, 4), dtype=np.uint8)
    if alpha <= 0.0:
        return out

    cx, cy = float(centre[0]), float(centre[1])
    ys, xs = np.indices((h, w), dtype=np.float32)
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    band = float(thickness) / 2.0
    # Black shadow (1 px outside the white ring) for legibility.
    shadow_mask = (
        (dist >= radius - band - 1.0)
        & (dist <= radius + band + 1.0)
    )
    out[shadow_mask] = _scale_alpha(HUD_SHADOW_COLOR, alpha)
    white_mask = (dist >= radius - band) & (dist <= radius + band)
    out[white_mask] = _scale_alpha(HUD_RING_COLOR, alpha)
    return out


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _scale_alpha(
    color: tuple[int, int, int, int], alpha_factor: float,
) -> tuple[int, int, int, int]:
    """Multiply an RGBA's alpha by ``alpha_factor``."""
    r, g, b, a = color
    return (
        int(r),
        int(g),
        int(b),
        max(0, min(255, int(round(a * float(alpha_factor))))),
    )


def fade_curve(
    elapsed_s: float, fade_duration_s: float = DEFAULT_FADE_DURATION_S,
) -> float:
    """Standalone helper exposing the same alpha curve as
    :meth:`SizeHudState.alpha_at` so tests can verify it without
    constructing a full state object."""
    if fade_duration_s <= 0:
        raise ValueError(
            f"fade_duration_s must be > 0, got {fade_duration_s!r}",
        )
    if elapsed_s <= 0:
        return 1.0
    if elapsed_s >= fade_duration_s:
        return 0.0
    return 1.0 - (float(elapsed_s) / float(fade_duration_s))
