"""Stacked layer compositing for non-destructive overlays.

A small, focused layer system that runs at the end of the develop pipeline
(after LUT, before masks). Each layer carries a kind (``text`` / ``image`` /
``lut``), an opacity, a blend mode, and a kind-specific ``params`` dict.
Layers are stored on the recipe as ``recipe.extra['layers']`` so they
round-trip through serialisation without touching the core schema.

Design choices:

* Pure numpy / PIL — no Qt — so it is unit-testable and reusable in batch
  export. A separate ``gui/layers_dialog.py`` module owns the editing UI.
* Blend modes operate on uint8 RGBA arrays. Opacity is the per-layer alpha
  scalar; the blend formula gives the *colour*, opacity controls how much
  of that colour reaches the base.
* Layer order matches the list: index 0 sits on top of the original image,
  index 1 on top of index 0's result, and so on. This lets users stack
  watermark over LUT over text without dialog gymnastics.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger("Imervue.layers")

LAYER_KINDS = ("text", "image", "lut")
BLEND_MODES = ("normal", "multiply", "screen", "overlay")
DEFAULT_OPACITY = 1.0
MAX_LAYERS = 8  # safety cap; matches Photoshop-style "few overlays" use case


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Layer:
    """One layer in the stack.

    ``params`` carries kind-specific data:

    * ``text``  → ``{"text": str, "corner": str, "color": [r, g, b], "font_fraction": float}``
    * ``image`` → ``{"path": str}``
    * ``lut``   → ``{"path": str, "intensity": float}``
    """

    kind: str = "text"
    enabled: bool = True
    opacity: float = DEFAULT_OPACITY
    blend_mode: str = "normal"
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "enabled": bool(self.enabled),
            "opacity": float(self.opacity),
            "blend_mode": self.blend_mode,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Layer:
        kind = str(data.get("kind", "text"))
        if kind not in LAYER_KINDS:
            kind = "text"
        blend_mode = str(data.get("blend_mode", "normal"))
        if blend_mode not in BLEND_MODES:
            blend_mode = "normal"
        return cls(
            kind=kind,
            enabled=bool(data.get("enabled", True)),
            opacity=_clamp01(float(data.get("opacity", DEFAULT_OPACITY))),
            blend_mode=blend_mode,
            params=dict(data.get("params") or {}),
        )


def layers_from_dict_list(raw: list) -> list[Layer]:
    """Deserialise a stored list of dicts. Skips malformed entries quietly."""
    result: list[Layer] = []
    if not raw:
        return result
    for entry in raw[:MAX_LAYERS]:
        if not isinstance(entry, dict):
            continue
        try:
            result.append(Layer.from_dict(entry))
        except (TypeError, ValueError) as exc:
            logger.debug("Skipping malformed layer entry: %s", exc)
    return result


def layers_to_dict_list(layers: list[Layer]) -> list[dict]:
    return [layer.to_dict() for layer in layers]


# ---------------------------------------------------------------------------
# Compositing pipeline
# ---------------------------------------------------------------------------


def apply_layers(arr: np.ndarray, layers: list[Layer]) -> np.ndarray:
    """Apply ``layers`` on top of ``arr`` in order. Returns a new array.

    Disabled layers and zero-opacity layers are skipped without rendering,
    so adding a layer and toggling it off costs nothing at apply time.
    """
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"apply_layers expects HxWx4 uint8 RGBA, got shape={arr.shape} dtype={arr.dtype}"
        )
    if not layers:
        return arr

    out = arr
    for layer in layers:
        if not layer.enabled or layer.opacity <= 0.0:
            continue
        rendered = _render_layer(out, layer)
        if rendered is None:
            continue
        out = _blend(out, rendered, layer.blend_mode, layer.opacity)
    return out


def _render_layer(base: np.ndarray, layer: Layer) -> np.ndarray | None:
    """Render this layer's pixel content sized to ``base``, or None on no-op."""
    if layer.kind == "text":
        return _render_text_layer(base, layer.params)
    if layer.kind == "image":
        return _render_image_layer(base, layer.params)
    if layer.kind == "lut":
        return _render_lut_layer(base, layer.params)
    return None


def _render_text_layer(base: np.ndarray, params: dict) -> np.ndarray | None:
    text = str(params.get("text", "")).strip()
    if not text:
        return None
    try:
        from Imervue.image.watermark import WatermarkOptions, apply_watermark
    except ImportError:
        return None
    color = params.get("color") or [255, 255, 255]
    try:
        rgb = (int(color[0]), int(color[1]), int(color[2]))
    except (IndexError, TypeError, ValueError):
        rgb = (255, 255, 255)
    opts = WatermarkOptions(
        text=text,
        corner=str(params.get("corner", "bottom-right")),
        opacity=1.0,  # opacity handled by blend stage
        font_fraction=float(params.get("font_fraction", 0.035)),
        color=rgb,
        shadow=bool(params.get("shadow", True)),
    )
    pil_base = Image.fromarray(base, mode="RGBA")
    rendered = apply_watermark(pil_base, opts)
    return np.array(rendered)


def _render_image_layer(base: np.ndarray, params: dict) -> np.ndarray | None:
    path = str(params.get("path", "")).strip()
    if not path or not Path(path).is_file():
        return None
    try:
        overlay = Image.open(path).convert("RGBA")
    except OSError as exc:
        logger.warning("Image layer load failed (%s): %s", path, exc)
        return None
    target = (base.shape[1], base.shape[0])
    if overlay.size != target:
        overlay = overlay.resize(target, Image.Resampling.LANCZOS)
    canvas = np.array(overlay)
    if canvas.shape != base.shape:
        # Force matching shape — resize above guarantees w/h, but the
        # alpha channel could still differ for grayscale source images.
        canvas = canvas.reshape(base.shape)
    return canvas


def _render_lut_layer(base: np.ndarray, params: dict) -> np.ndarray | None:
    lut_path = str(params.get("path", "")).strip()
    if not lut_path:
        return None
    try:
        from Imervue.image.lut import apply_cube_lut
    except ImportError:
        return None
    intensity = _clamp01(float(params.get("intensity", 1.0)))
    try:
        return apply_cube_lut(base, lut_path, intensity=intensity)
    except (OSError, ValueError) as exc:
        logger.warning("LUT layer apply failed (%s): %s", lut_path, exc)
        return None


# ---------------------------------------------------------------------------
# Blending
# ---------------------------------------------------------------------------


def _blend(
    base: np.ndarray,
    overlay: np.ndarray,
    mode: str,
    opacity: float,
) -> np.ndarray:
    """Composite ``overlay`` onto ``base`` using ``mode`` and ``opacity``.

    Both arrays are HxWx4 uint8. Opacity scales the overlay's alpha
    channel before the blend formula chooses the final colour.
    """
    base_rgb = base[..., :3].astype(np.float32) / 255.0
    overlay_rgb = overlay[..., :3].astype(np.float32) / 255.0

    blended = _apply_blend_formula(base_rgb, overlay_rgb, mode)

    # Effective alpha = overlay alpha × user opacity
    overlay_alpha = (overlay[..., 3:4].astype(np.float32) / 255.0) * _clamp01(opacity)
    final_rgb = base_rgb * (1.0 - overlay_alpha) + blended * overlay_alpha

    out = np.empty_like(base)
    out[..., :3] = np.clip(final_rgb * 255.0, 0.0, 255.0).astype(np.uint8)
    out[..., 3] = base[..., 3]
    return out


def _apply_blend_formula(base: np.ndarray, overlay: np.ndarray, mode: str) -> np.ndarray:
    """Per-mode pixel formula on float32 ``[0, 1]`` RGB arrays."""
    if mode == "multiply":
        return base * overlay
    if mode == "screen":
        return 1.0 - (1.0 - base) * (1.0 - overlay)
    if mode == "overlay":
        # Standard overlay: low-light → multiply, high-light → screen
        low = 2.0 * base * overlay
        high = 1.0 - 2.0 * (1.0 - base) * (1.0 - overlay)
        return np.where(base < 0.5, low, high)
    # default = "normal"
    return overlay


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
