"""Clone stamp — copy a source patch onto a destination with soft feather.

Complements :mod:`Imervue.image.healing`: healing reconstructs texture from
the neighbourhood (good for dust spots), while clone stamp does an exact
source-to-destination copy (good for duplicating or replacing content).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.clone_stamp")

_MAX_STAMPS = 256


@dataclass(frozen=True)
class CloneStamp:
    """A single clone stamp operation: copy (sx, sy) → (dx, dy) with radius."""

    sx: int
    sy: int
    dx: int
    dy: int
    radius: int
    feather: float = 0.5          # 0..1 fraction of radius

    def to_dict(self) -> dict:
        return {
            "sx": self.sx, "sy": self.sy,
            "dx": self.dx, "dy": self.dy,
            "r": self.radius, "f": self.feather,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CloneStamp":
        return cls(
            sx=int(data["sx"]), sy=int(data["sy"]),
            dx=int(data["dx"]), dy=int(data["dy"]),
            radius=max(1, int(data.get("r", 20))),
            feather=max(0.0, min(1.0, float(data.get("f", 0.5)))),
        )


def stamps_to_dict_list(stamps: list[CloneStamp]) -> list[dict]:
    return [s.to_dict() for s in stamps[:_MAX_STAMPS]]


def stamps_from_dict_list(items: list[dict]) -> list[CloneStamp]:
    out: list[CloneStamp] = []
    for it in (items or [])[:_MAX_STAMPS]:
        if not isinstance(it, dict):
            continue
        try:
            out.append(CloneStamp.from_dict(it))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _feather_mask(radius: int, feather: float) -> np.ndarray:
    d = 2 * radius + 1
    y, x = np.indices((d, d), dtype=np.float32) - radius
    dist = np.sqrt(x * x + y * y)
    inner = radius * (1.0 - feather)
    outer = radius
    if outer - inner < 1e-3:
        return (dist <= radius).astype(np.float32)
    t = np.clip((outer - dist) / (outer - inner), 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def _blit(
    canvas: np.ndarray, src_patch: np.ndarray, dx: int, dy: int, mask: np.ndarray,
) -> None:
    h, w = canvas.shape[:2]
    ph, pw = src_patch.shape[:2]
    x0 = dx - pw // 2
    y0 = dy - ph // 2
    cx0 = max(0, x0); cy0 = max(0, y0)
    cx1 = min(w, x0 + pw); cy1 = min(h, y0 + ph)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    sx0 = cx0 - x0; sy0 = cy0 - y0
    sx1 = sx0 + (cx1 - cx0); sy1 = sy0 + (cy1 - cy0)
    region = canvas[cy0:cy1, cx0:cx1, :3].astype(np.float32)
    patch = src_patch[sy0:sy1, sx0:sx1, :3].astype(np.float32)
    m = mask[sy0:sy1, sx0:sx1][..., None]
    canvas[cy0:cy1, cx0:cx1, :3] = np.clip(
        region * (1.0 - m) + patch * m, 0.0, 255.0,
    ).astype(np.uint8)


def apply_clone_stamp(
    arr: np.ndarray, stamps: list[CloneStamp],
) -> np.ndarray:
    """Apply each clone stamp in order. Returns a new HxWx4 RGBA array."""
    if not stamps:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("apply_clone_stamp expects HxWx4 RGBA uint8")
    out = arr.copy()
    h, w = out.shape[:2]
    for stamp in stamps:
        radius = max(1, int(stamp.radius))
        sx, sy = int(stamp.sx), int(stamp.sy)
        if not (0 <= sx < w and 0 <= sy < h):
            continue
        # Extract source patch from the current canvas (so chained stamps
        # can sample each other's output — matches Photoshop behaviour).
        x0 = sx - radius; y0 = sy - radius
        x1 = sx + radius + 1; y1 = sy + radius + 1
        px0 = max(0, x0); py0 = max(0, y0)
        px1 = min(w, x1); py1 = min(h, y1)
        if px1 <= px0 or py1 <= py0:
            continue
        patch = np.zeros((2 * radius + 1, 2 * radius + 1, 4), dtype=np.uint8)
        patch[py0 - y0:py1 - y0, px0 - x0:px1 - x0] = out[py0:py1, px0:px1]
        mask = _feather_mask(radius, stamp.feather)
        _blit(out, patch, int(stamp.dx), int(stamp.dy), mask)
    return out
