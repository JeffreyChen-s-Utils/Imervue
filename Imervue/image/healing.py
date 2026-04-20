"""
Healing brush / spot removal — OpenCV inpainting over user-painted masks.

A *healing spot* is a circular mask position where the user wants the
nearby background texture reconstructed over an unwanted feature (dust
spot, stray wire, pimple). We store spots as a simple list so they
round-trip through Recipe.extra without bloating the Recipe dataclass.

Two inpaint algorithms are exposed:

- ``telea`` — Fast Marching Method (``cv2.INPAINT_TELEA``); fast, good on
  small spots (1-20 px radius).
- ``ns`` — Navier-Stokes (``cv2.INPAINT_NS``); slower but blends textures
  more smoothly, better for larger patches.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.healing")

_METHODS = {"telea", "ns"}
_MAX_SPOTS = 512


@dataclass(frozen=True)
class HealingSpot:
    """A single healing spot on the image (coordinates in image pixels)."""

    x: int
    y: int
    radius: int
    method: str = "telea"

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "r": self.radius, "m": self.method}

    @classmethod
    def from_dict(cls, data: dict) -> "HealingSpot":
        method = str(data.get("m", "telea"))
        if method not in _METHODS:
            method = "telea"
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            radius=max(1, int(data.get("r", 5))),
            method=method,
        )


def spots_from_dict_list(items: list[dict]) -> list[HealingSpot]:
    out: list[HealingSpot] = []
    for it in items[:_MAX_SPOTS]:
        if not isinstance(it, dict):
            continue
        try:
            out.append(HealingSpot.from_dict(it))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def spots_to_dict_list(spots: list[HealingSpot]) -> list[dict]:
    return [s.to_dict() for s in spots]


def _build_mask(
    shape: tuple[int, int], spots: list[HealingSpot], method: str,
) -> np.ndarray:
    import cv2
    mask = np.zeros(shape, dtype=np.uint8)
    for s in spots:
        if s.method != method:
            continue
        cv2.circle(mask, (s.x, s.y), max(1, s.radius), color=255, thickness=-1)
    return mask


def apply_healing(arr: np.ndarray, spots: list[HealingSpot]) -> np.ndarray:
    """Apply inpainting for each healing spot. Returns a new HxWx4 RGBA array."""
    if not spots:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("apply_healing expects HxWx4 RGBA uint8")

    import cv2
    bgr = arr[..., [2, 1, 0]].copy()
    shape = arr.shape[:2]

    for method, cv_flag in (("telea", cv2.INPAINT_TELEA), ("ns", cv2.INPAINT_NS)):
        mask = _build_mask(shape, spots, method)
        if mask.any():
            # Radius of 3 is a good default for fast-marching neighbourhood.
            bgr = cv2.inpaint(bgr, mask, 3, cv_flag)

    out = arr.copy()
    out[..., 0] = bgr[..., 2]
    out[..., 1] = bgr[..., 1]
    out[..., 2] = bgr[..., 0]
    return out
