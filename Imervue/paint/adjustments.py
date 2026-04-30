"""Pure-numpy non-destructive adjustment kinds + apply pipeline.

An :class:`Adjustment` is a lightweight, frozen dataclass that names
one of the supported transforms (``levels`` / ``curves`` / ``hsv``)
plus a parameter dict. The compositor applies these to the running
canvas buffer at render time, so the user can tune the parameters
later without reflowing every layer underneath — the destructive
"flatten" + "filter" loop is no longer required.

Kinds (all operate on 8-bit RGB; the alpha channel is left untouched
since adjustment layers shouldn't change visibility):

* ``levels``:   ``input_black``, ``input_white``, ``gamma``,
                ``output_black``, ``output_white`` — Photoshop's
                Levels dialog.
* ``curves``:   ``points`` — list of ``[input, output]`` control
                points in ``[0, 255]``; piecewise-linear LUT in between.
* ``hsv``:      ``hue_shift_deg``, ``saturation``, ``lightness`` —
                rotate hue + scale S / V channels.

The dispatch entry point is :func:`apply_adjustment`. New kinds can
be added by extending ``ADJUSTMENT_KINDS`` + the dispatch table.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

ADJUSTMENT_KINDS = ("levels", "curves", "hsv")

DEFAULT_PARAMS: dict[str, dict] = {
    "levels": {
        "input_black": 0,
        "input_white": 255,
        "gamma": 1.0,
        "output_black": 0,
        "output_white": 255,
    },
    "curves": {
        "points": [[0, 0], [255, 255]],
    },
    "hsv": {
        "hue_shift_deg": 0.0,
        "saturation": 1.0,
        "lightness": 1.0,
    },
}


@dataclass(frozen=True)
class Adjustment:
    """One non-destructive adjustment + its parameter dict."""

    kind: str
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in ADJUSTMENT_KINDS:
            raise ValueError(
                f"unknown adjustment kind {self.kind!r}; "
                f"expected one of {ADJUSTMENT_KINDS}",
            )
        if not isinstance(self.params, dict):
            raise ValueError(
                f"params must be a dict, got {type(self.params).__name__}",
            )

    def to_dict(self) -> dict:
        return {"kind": self.kind, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, raw: dict) -> Adjustment:
        if not isinstance(raw, dict):
            raise ValueError(
                f"adjustment payload must be a dict, got {type(raw).__name__}",
            )
        kind = str(raw.get("kind", "")).strip()
        if kind not in ADJUSTMENT_KINDS:
            raise ValueError(f"unknown adjustment kind {kind!r}")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}
        merged = {**DEFAULT_PARAMS[kind], **params}
        return cls(kind=kind, params=merged)


# ---------------------------------------------------------------------------
# Apply dispatch
# ---------------------------------------------------------------------------


def apply_adjustment(
    image: np.ndarray, adjustment: Adjustment,
) -> np.ndarray:
    """Return a fresh HxWx4 uint8 image with the adjustment applied.

    The alpha channel is preserved. Out-of-range parameters are
    clamped to safe values so a corrupt persisted Adjustment can't
    explode the renderer.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    if adjustment.kind == "levels":
        return _apply_levels(image, adjustment.params)
    if adjustment.kind == "curves":
        return _apply_curves(image, adjustment.params)
    if adjustment.kind == "hsv":
        return _apply_hsv(image, adjustment.params)
    raise ValueError(f"unknown adjustment kind {adjustment.kind!r}")


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------


def _apply_levels(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["levels"], **params}
    in_black = max(0, min(255, int(p.get("input_black", 0))))
    in_white = max(in_black + 1, min(255, int(p.get("input_white", 255))))
    out_black = max(0, min(255, int(p.get("output_black", 0))))
    out_white = max(0, min(255, int(p.get("output_white", 255))))
    gamma = max(0.01, min(10.0, float(p.get("gamma", 1.0))))

    rgb = image[..., :3].astype(np.float32) / 255.0
    in_b = in_black / 255.0
    in_w = in_white / 255.0
    out_b = out_black / 255.0
    out_w = out_white / 255.0

    stretched = np.clip((rgb - in_b) / max(in_w - in_b, 1e-6), 0.0, 1.0)
    gamma_corrected = np.power(stretched, 1.0 / gamma)
    mapped = out_b + gamma_corrected * (out_w - out_b)

    out = image.copy()
    out[..., :3] = np.clip(mapped * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# Curves
# ---------------------------------------------------------------------------


def _apply_curves(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["curves"], **params}
    raw_points = p.get("points") or DEFAULT_PARAMS["curves"]["points"]
    points = sorted(
        (
            (max(0, min(255, int(pt[0]))), max(0, min(255, int(pt[1]))))
            for pt in raw_points
            if isinstance(pt, (list, tuple)) and len(pt) == 2
        ),
        key=lambda pt: pt[0],
    )
    if len(points) < 2:
        # Need at least two points to define a curve; fall back to identity.
        return image.copy()

    xs = np.array([pt[0] for pt in points], dtype=np.float32)
    ys = np.array([pt[1] for pt in points], dtype=np.float32)
    lut = np.interp(np.arange(256, dtype=np.float32), xs, ys)
    lut_u8 = np.clip(lut, 0, 255).astype(np.uint8)

    out = image.copy()
    out[..., 0] = lut_u8[image[..., 0]]
    out[..., 1] = lut_u8[image[..., 1]]
    out[..., 2] = lut_u8[image[..., 2]]
    return out


# ---------------------------------------------------------------------------
# HSV
# ---------------------------------------------------------------------------


def _apply_hsv(image: np.ndarray, params: dict) -> np.ndarray:
    p = {**DEFAULT_PARAMS["hsv"], **params}
    hue_shift = float(p.get("hue_shift_deg", 0.0))
    saturation = max(0.0, min(8.0, float(p.get("saturation", 1.0))))
    lightness = max(0.0, min(8.0, float(p.get("lightness", 1.0))))
    rgb = image[..., :3].astype(np.float32) / 255.0
    hsv = _rgb_to_hsv(rgb)
    hsv[..., 0] = (hsv[..., 0] + hue_shift) % 360.0
    hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0.0, 1.0)
    hsv[..., 2] = np.clip(hsv[..., 2] * lightness, 0.0, 1.0)
    rgb_out = _hsv_to_rgb(hsv)
    out = image.copy()
    out[..., :3] = np.clip(rgb_out * 255.0, 0.0, 255.0).astype(np.uint8)
    return out


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Vectorised RGB → HSV. Inputs / outputs are HxWx3 float32 in
    [0, 1] (S, V) and [0, 360) (H)."""
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    cmax = np.max(rgb, axis=-1)
    cmin = np.min(rgb, axis=-1)
    delta = cmax - cmin
    safe_delta = np.where(delta == 0, 1.0, delta)

    h = np.zeros_like(cmax)
    mask_r = (cmax == r) & (delta != 0)
    mask_g = (cmax == g) & (delta != 0)
    mask_b = (cmax == b) & (delta != 0)
    h = np.where(mask_r, ((g - b) / safe_delta) % 6.0, h)
    h = np.where(mask_g, ((b - r) / safe_delta) + 2.0, h)
    h = np.where(mask_b, ((r - g) / safe_delta) + 4.0, h)
    h = h * 60.0

    s = np.where(cmax == 0, 0.0, delta / np.where(cmax == 0, 1.0, cmax))
    v = cmax
    return np.stack([h, s, v], axis=-1)


def _hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    """Inverse of :func:`_rgb_to_hsv`. Accepts H in any range; result
    is HxWx3 float32 in [0, 1]."""
    h = hsv[..., 0] % 360.0
    s = hsv[..., 1]
    v = hsv[..., 2]
    c = v * s
    h_prime = h / 60.0
    x = c * (1.0 - np.abs(h_prime % 2.0 - 1.0))
    m = v - c

    r = np.zeros_like(c)
    g = np.zeros_like(c)
    b = np.zeros_like(c)

    seg0 = (h_prime >= 0) & (h_prime < 1)
    seg1 = (h_prime >= 1) & (h_prime < 2)
    seg2 = (h_prime >= 2) & (h_prime < 3)
    seg3 = (h_prime >= 3) & (h_prime < 4)
    seg4 = (h_prime >= 4) & (h_prime < 5)
    seg5 = (h_prime >= 5) & (h_prime < 6)

    r = np.where(seg0, c, r)
    g = np.where(seg0, x, g)
    r = np.where(seg1, x, r)
    g = np.where(seg1, c, g)
    g = np.where(seg2, c, g)
    b = np.where(seg2, x, b)
    g = np.where(seg3, x, g)
    b = np.where(seg3, c, b)
    r = np.where(seg4, x, r)
    b = np.where(seg4, c, b)
    r = np.where(seg5, c, r)
    b = np.where(seg5, x, b)

    return np.stack([r + m, g + m, b + m], axis=-1)
