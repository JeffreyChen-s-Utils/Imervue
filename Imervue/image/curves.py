"""Curves adjustment — RGB / per-channel tone mapping via control points.

Where :mod:`Imervue.image.levels` is two endpoints + gamma, Curves
exposes an arbitrary number of control points the user can drag on
a 0..255 input → 0..255 output graph. The shape between points is
interpolated; a few canonical presets cover the common edits
("S-curve" for contrast, "lift shadows", "compress highlights")
without forcing every artist to learn the curve UI.

The module is pure-numpy and Qt-free so the curve maths can be
exercised in unit tests without a display server. The Filter-menu
dialog renders a small interactive curve editor that drives the
``points`` field of :class:`CurveOptions` and re-builds the LUT on
every drag.

Channel keys
------------

``"rgb"`` is the master / luminance curve applied to all three RGB
channels uniformly. ``"r"`` / ``"g"`` / ``"b"`` are per-channel
curves layered on top of the master, in that order. Alpha is never
touched — Curves is a tone tool, not a transparency tool.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("Imervue.curves")

CURVE_CHANNELS = ("rgb", "r", "g", "b")
DEFAULT_CHANNEL = "rgb"

CURVE_INPUT_MIN = 0
CURVE_INPUT_MAX = 255
CURVE_OUTPUT_MIN = 0
CURVE_OUTPUT_MAX = 255

# A "no-op" curve maps every input to the same output. Used as the
# default when a channel has no control points so the LUT path is
# still safe to call.
IDENTITY_POINTS: tuple[tuple[int, int], ...] = (
    (CURVE_INPUT_MIN, CURVE_OUTPUT_MIN),
    (CURVE_INPUT_MAX, CURVE_OUTPUT_MAX),
)


@dataclass
class CurveOptions:
    """One CurveOptions describes the four channel curves at once.

    ``per_channel`` keys must come from :data:`CURVE_CHANNELS`; any
    missing key is treated as identity. Stored as plain lists of
    (x, y) tuples so JSON round-trips trivially.
    """

    enabled: bool = False
    per_channel: dict[str, tuple[tuple[int, int], ...]] = field(
        default_factory=lambda: dict.fromkeys(CURVE_CHANNELS, IDENTITY_POINTS),
    )

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "per_channel": {
                ch: [list(p) for p in self.per_channel.get(ch, IDENTITY_POINTS)]
                for ch in CURVE_CHANNELS
            },
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> CurveOptions:
        if not isinstance(data, dict):
            return cls()
        per: dict[str, tuple[tuple[int, int], ...]] = {}
        raw = data.get("per_channel", {})
        if not isinstance(raw, dict):
            raw = {}
        for ch in CURVE_CHANNELS:
            entries = raw.get(ch)
            per[ch] = (
                _normalise_points(entries) if entries is not None
                else IDENTITY_POINTS
            )
        return cls(
            enabled=bool(data.get("enabled", False)),
            per_channel=per,
        )


def build_lut(points: Sequence[tuple[int, int]]) -> np.ndarray:
    """Return a 256-entry uint8 LUT interpolating between ``points``.

    Points are sorted by input-x; duplicate x-values keep the last
    occurrence (so a click+drag onto an existing point overwrites
    rather than producing an undefined zero-width segment). The
    function never raises on out-of-range values — input x is
    clamped into [0, 255] and y into [0, 255] so a corrupted persisted
    curve can't crash the renderer.
    """
    sanitized = _normalise_points(points)
    xs = np.array([p[0] for p in sanitized], dtype=np.float32)
    ys = np.array([p[1] for p in sanitized], dtype=np.float32)
    indices = np.arange(256, dtype=np.float32)
    interpolated = np.interp(indices, xs, ys)
    return np.clip(interpolated + 0.5, 0, 255).astype(np.uint8)


def apply_curves(arr: np.ndarray, options: CurveOptions) -> np.ndarray:
    """Apply ``options`` to ``arr`` and return a new HxWx4 RGBA array.

    The order is **master → per-channel** so a per-channel adjustment
    layers on top of the master remap (matches Photoshop's behaviour).
    Identity curves short-circuit so unchanged channels pay nothing.
    """
    if not options.enabled:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_curves expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
        )
    master = options.per_channel.get("rgb", IDENTITY_POINTS)
    per_r = options.per_channel.get("r", IDENTITY_POINTS)
    per_g = options.per_channel.get("g", IDENTITY_POINTS)
    per_b = options.per_channel.get("b", IDENTITY_POINTS)
    if (
        _is_identity(master)
        and _is_identity(per_r)
        and _is_identity(per_g)
        and _is_identity(per_b)
    ):
        return arr
    out = arr.copy()
    rgb = out[..., :3]
    if not _is_identity(master):
        master_lut = build_lut(master)
        rgb = master_lut.take(rgb)
    if not _is_identity(per_r):
        rgb[..., 0] = build_lut(per_r).take(rgb[..., 0])
    if not _is_identity(per_g):
        rgb[..., 1] = build_lut(per_g).take(rgb[..., 1])
    if not _is_identity(per_b):
        rgb[..., 2] = build_lut(per_b).take(rgb[..., 2])
    out[..., :3] = rgb
    return out


# ---------------------------------------------------------------------------
# Presets — quick starting points for the dialog
# ---------------------------------------------------------------------------


def s_curve_preset(strength: float = 0.15) -> tuple[tuple[int, int], ...]:
    """Classic S-curve: lift highlights, drop shadows for more contrast.

    ``strength`` 0..0.5 controls how aggressive the curve is; 0
    returns identity, 0.5 produces a near-binary contrast.
    """
    s = max(0.0, min(0.5, float(strength)))
    delta = int(round(s * 255))
    return (
        (0, 0),
        (64, max(0, 64 - delta)),
        (192, min(255, 192 + delta)),
        (255, 255),
    )


def lift_shadows_preset(amount: float = 0.2) -> tuple[tuple[int, int], ...]:
    """Pull dark midtones up without touching highlights — flat-light look."""
    a = max(0.0, min(0.4, float(amount)))
    bump = int(round(a * 255))
    return (
        (0, min(255, bump)),
        (128, min(255, 128 + bump // 2)),
        (255, 255),
    )


def compress_highlights_preset(amount: float = 0.2) -> tuple[tuple[int, int], ...]:
    """Pull bright pixels down so a clipping highlight regains detail."""
    a = max(0.0, min(0.4, float(amount)))
    drop = int(round(a * 255))
    return (
        (0, 0),
        (128, max(0, 128 - drop // 2)),
        (255, max(0, 255 - drop)),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _normalise_points(
    raw,
) -> tuple[tuple[int, int], ...]:
    """Return a sanitised, sorted-by-x tuple of (int x, int y) points.

    Drops entries that don't look like 2-element coordinates. Clamps
    every survivor into the valid 0..255 range. Always returns at
    least the two identity endpoints so the LUT builder never sees
    an empty input.
    """
    out: list[tuple[int, int]] = []
    seen_x: set[int] = set()
    if not isinstance(raw, (list, tuple)):
        raw = ()
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        try:
            x = int(round(float(entry[0])))
            y = int(round(float(entry[1])))
        except (TypeError, ValueError):
            continue
        x = max(CURVE_INPUT_MIN, min(CURVE_INPUT_MAX, x))
        y = max(CURVE_OUTPUT_MIN, min(CURVE_OUTPUT_MAX, y))
        # Keep the LAST occurrence per x to mirror "drag onto existing
        # point overwrites" — pop the previous tuple with the same x.
        if x in seen_x:
            out = [p for p in out if p[0] != x]
        seen_x.add(x)
        out.append((x, y))
    if not out:
        return IDENTITY_POINTS
    out.sort(key=lambda p: p[0])
    # Pad endpoints so np.interp never extrapolates.
    if out[0][0] != CURVE_INPUT_MIN:
        out.insert(0, (CURVE_INPUT_MIN, out[0][1]))
    if out[-1][0] != CURVE_INPUT_MAX:
        out.append((CURVE_INPUT_MAX, out[-1][1]))
    return tuple(out)


def _is_identity(points: Sequence[tuple[int, int]]) -> bool:
    """Cheap check — exactly the two identity endpoints, in order."""
    if len(points) != 2:
        return False
    (x0, y0), (x1, y1) = points[0], points[1]
    return x0 == y0 == CURVE_INPUT_MIN and x1 == y1 == CURVE_INPUT_MAX
