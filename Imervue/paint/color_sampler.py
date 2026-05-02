"""Persistent color sampler points — Photoshop's "Color Sampler" tool.

Pin up to N named ``(x, y)`` markers on the canvas; each one reads
the composite RGBA at render time and the panel widget displays the
live values. Unlike the eyedropper (which fires once per click),
sampler points stay put and update with every paint stroke so the
user can verify a tonal target while painting.

Pure data + numpy reads; the panel widget renders the text readouts.
The model holds the points list + an optional name-keyed lookup;
persistence rounds through ``user_setting_dict``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_color_sampler"
MAX_SAMPLER_POINTS = 16


@dataclass(frozen=True)
class SamplerPoint:
    """One named (x, y) marker."""

    name: str
    x: int
    y: int
    visible: bool = True

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("sampler point name must be non-empty")

    def to_dict(self) -> dict:
        return {
            "name": str(self.name),
            "x": int(self.x),
            "y": int(self.y),
            "visible": bool(self.visible),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> SamplerPoint:
        if not isinstance(raw, dict):
            raise ValueError(
                f"sampler payload must be a dict, got {type(raw).__name__}",
            )
        # Pass the raw name through so __post_init__ rejects blanks —
        # a silently-renamed sampler would collide with other entries
        # and confuse the readout panel.
        return cls(
            name=str(raw.get("name", "")).strip(),
            x=int(raw.get("x", 0)),
            y=int(raw.get("y", 0)),
            visible=bool(raw.get("visible", True)),
        )


@dataclass
class ColorSampler:
    """Mutable container for an ordered list of SamplerPoints."""

    points: list[SamplerPoint] = field(default_factory=list)

    def add(self, point: SamplerPoint) -> bool:
        """Append a point. Returns ``False`` when the cap is hit or
        the name collides with an existing point."""
        if len(self.points) >= MAX_SAMPLER_POINTS:
            return False
        if any(p.name == point.name for p in self.points):
            return False
        self.points.append(point)
        return True

    def remove(self, name: str) -> bool:
        """Drop the point with ``name`` if present."""
        for i, p in enumerate(self.points):
            if p.name == name:
                del self.points[i]
                return True
        return False

    def find(self, name: str) -> SamplerPoint | None:
        for p in self.points:
            if p.name == name:
                return p
        return None

    def clear(self) -> None:
        self.points = []

    def to_dict(self) -> dict:
        return {"points": [p.to_dict() for p in self.points]}

    @classmethod
    def from_dict(cls, raw: dict) -> ColorSampler:
        if not isinstance(raw, dict):
            return cls()
        out = cls()
        for entry in (raw.get("points") or [])[:MAX_SAMPLER_POINTS]:
            try:
                out.points.append(SamplerPoint.from_dict(entry))
            except (ValueError, TypeError):
                continue
        return out


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def read_at(
    image: np.ndarray, point: SamplerPoint,
) -> tuple[int, int, int, int] | None:
    """Read the RGBA at ``point`` from an HxWx4 uint8 buffer.

    Returns ``None`` when the point falls outside the buffer; the
    panel widget shows "—" in that case rather than guessing."""
    if (
        image.ndim != 3
        or image.shape[2] != 4
        or image.dtype != np.uint8
    ):
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    h, w = image.shape[:2]
    x = int(point.x)
    y = int(point.y)
    if not (0 <= x < w and 0 <= y < h):
        return None
    pixel = image[y, x]
    return (
        int(pixel[0]), int(pixel[1]), int(pixel[2]), int(pixel[3]),
    )


def read_all(
    image: np.ndarray, sampler: ColorSampler,
) -> dict[str, tuple[int, int, int, int] | None]:
    """Read every visible point in ``sampler``. Returns a name → RGBA
    (or ``None`` for off-canvas / hidden) mapping in insertion order."""
    out: dict[str, tuple[int, int, int, int] | None] = {}
    for point in sampler.points:
        if not point.visible:
            out[point.name] = None
            continue
        out[point.name] = read_at(image, point)
    return out


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_sampler(sampler: ColorSampler) -> None:
    user_setting_dict[_USER_SETTING_KEY] = sampler.to_dict()
    schedule_save()


def load_sampler() -> ColorSampler:
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, dict):
        return ColorSampler()
    return ColorSampler.from_dict(raw)
