"""Gradient Map adjustment kind: luminance through a multi-stop LUT.

Dispatched by :mod:`Imervue.paint.adjustments`.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.adjustments_params import DEFAULT_PARAMS


def _apply_gradient_map(image: np.ndarray, params: dict) -> np.ndarray:
    """Map per-pixel luminance to a multi-stop gradient lookup."""
    p = {**DEFAULT_PARAMS["gradient_map"], **params}
    stops_raw = p.get("stops") or DEFAULT_PARAMS["gradient_map"]["stops"]
    lut = _build_gradient_lut(stops_raw)
    rgb = image[..., :3].astype(np.float32)
    luminance = (
        0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    )
    indices = np.clip(np.rint(luminance), 0, 255).astype(np.int32)
    mapped = lut[indices]
    out = image.copy()
    out[..., :3] = mapped[..., :3]
    return out


def _build_gradient_lut(stops_raw) -> np.ndarray:
    """Compile a list of {position, color} stops into a 256×4 uint8
    LUT. Ill-formed stops are dropped; if fewer than 2 valid stops
    remain the default black→white pair pads it out."""
    cleaned: list[tuple[float, tuple[int, int, int, int]]] = []
    for entry in stops_raw or []:
        parsed = _parse_gradient_stop(entry)
        if parsed is not None:
            cleaned.append(parsed)
    cleaned.sort(key=lambda pair: pair[0])
    if len(cleaned) < 2:
        cleaned = [
            (0.0, (0, 0, 0, 255)),
            (1.0, (255, 255, 255, 255)),
        ]

    positions = np.array([c[0] for c in cleaned], dtype=np.float32) * 255.0
    colors = np.array([c[1] for c in cleaned], dtype=np.float32)
    lut = np.zeros((256, 4), dtype=np.float32)
    for ch in range(4):
        lut[:, ch] = np.interp(np.arange(256, dtype=np.float32), positions, colors[:, ch])
    return np.clip(lut, 0.0, 255.0).astype(np.uint8)


def _parse_gradient_stop(
    entry,
) -> tuple[float, tuple[int, int, int, int]] | None:
    """Coerce one ``{"position", "color"}`` blob into a clean
    ``(position, rgba)`` tuple. Returns ``None`` if the entry has the
    wrong shape so the caller can drop it cleanly."""
    if not isinstance(entry, dict):
        return None
    try:
        position = max(0.0, min(1.0, float(entry.get("position", 0.0))))
    except (TypeError, ValueError):
        return None
    color = _parse_gradient_color(entry.get("color"))
    if color is None:
        return None
    return (position, color)


def _parse_gradient_color(
    raw_color,
) -> tuple[int, int, int, int] | None:
    """Convert an optional 3- or 4-element colour list into an RGBA
    ``(0..255, ...)`` tuple. ``None`` when the layout is invalid;
    missing alpha falls back to fully opaque."""
    if raw_color is None:
        return (0, 0, 0, 255)
    if not isinstance(raw_color, list | tuple) or len(raw_color) < 3:
        return None
    try:
        if len(raw_color) >= 4:
            return tuple(max(0, min(255, int(c))) for c in raw_color[:4])
        return (
            *(max(0, min(255, int(c))) for c in raw_color[:3]),
            255,
        )
    except (TypeError, ValueError):
        return None
