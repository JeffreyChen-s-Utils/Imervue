"""Portrait relighting — heuristic shading + optional ONNX inference.

Two shipping methods:

* :func:`heuristic_relight` — pure-numpy. Estimates a surface-normal
  proxy from luma gradients (Sobel), computes a Lambert dot-product
  against a user-controlled directional light, and modulates the
  original RGB by ``1 + intensity * shading``. Adds a colour-temperature
  shift to the highlights so warm/cold lighting reads correctly.
  Doesn't try to be a true relight — it's a directional fill that
  responds to existing subject geometry.
* :func:`onnx_relight` — loads DPR / SwitchLight-style ONNX models
  from ``plugins/ai_portrait_relight/models/`` and runs them via
  ``onnxruntime``. Models that need a target spherical-harmonic
  light vector are not yet supported; this path is for end-to-end
  RGB→RGB relighters.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

AZIMUTH_MIN = 0
AZIMUTH_MAX = 360
ELEVATION_MIN = -90
ELEVATION_MAX = 90
INTENSITY_MIN = 0.0
INTENSITY_MAX = 2.0
TEMPERATURE_MIN = -100
TEMPERATURE_MAX = 100
BLEND_MIN = 0.0
BLEND_MAX = 1.0


@dataclass(frozen=True)
class RelightOptions:
    """Tuning for :func:`heuristic_relight`."""

    azimuth: float = 45.0          # degrees, 0 = right, 90 = up (image-space)
    elevation: float = 30.0        # degrees, positive = light coming from front
    intensity: float = 0.6         # multiplies the shading map
    temperature: int = 0           # -100 (cool) .. +100 (warm)
    blend: float = 1.0             # mix with original


def heuristic_relight(arr: np.ndarray, options: RelightOptions | None = None) -> np.ndarray:
    """Apply heuristic directional shading + colour-temperature shift."""
    _check_input(arr)
    options = options or RelightOptions()
    blend = max(BLEND_MIN, min(BLEND_MAX, float(options.blend)))
    if blend <= 0.0:
        return arr.copy()

    rgb = arr[..., :3].astype(np.float32) / 255.0
    luma = (
        0.2126 * rgb[..., 0]
        + 0.7152 * rgb[..., 1]
        + 0.0722 * rgb[..., 2]
    )

    shading = _shading_from_luma(luma, options.azimuth, options.elevation)
    intensity = max(INTENSITY_MIN, min(INTENSITY_MAX, float(options.intensity)))
    relit = rgb * (1.0 + intensity * shading[..., None])

    relit = _apply_temperature_shift(relit, options.temperature, shading)
    relit = np.clip(relit, 0.0, 1.0)

    if blend < 1.0:
        relit = rgb * (1.0 - blend) + relit * blend

    out = np.empty_like(arr)
    out[..., :3] = (relit * 255.0).astype(np.uint8)
    out[..., 3] = arr[..., 3]
    return out


def onnx_relight(arr: np.ndarray, model_path: str | Path, *, blend: float = 1.0) -> np.ndarray:
    """Run a user-supplied end-to-end ONNX relight model.

    Expects NCHW float32 ``[0, 1]`` input and matching output. Models
    requiring an extra light-direction tensor are not handled here.
    """
    _check_input(arr)
    blend = max(BLEND_MIN, min(BLEND_MAX, float(blend)))
    if blend <= 0.0:
        return arr.copy()

    import onnxruntime as ort

    session = ort.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"],
    )
    rgb = arr[..., :3].astype(np.float32) / 255.0
    nchw = rgb.transpose(2, 0, 1)[None, ...]
    input_name = session.get_inputs()[0].name
    raw = session.run(None, {input_name: nchw})[0]
    if raw.ndim == 4:
        out_chw = raw[0]
    elif raw.ndim == 3:
        out_chw = raw
    else:
        raise ValueError(
            f"ONNX relight model returned unexpected rank {raw.ndim}",
        )
    out_rgb = np.clip(out_chw.transpose(1, 2, 0), 0.0, 1.0)

    if blend < 1.0:
        out_rgb = rgb * (1.0 - blend) + out_rgb * blend

    out = np.empty_like(arr)
    out[..., :3] = (out_rgb * 255.0).astype(np.uint8)
    out[..., 3] = arr[..., 3]
    return out


def light_direction(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """Convert spherical (az, el) to a unit Cartesian vector.

    Image-space convention: x = right, y = up, z = toward viewer.
    """
    az = np.deg2rad(_clamp(azimuth_deg, AZIMUTH_MIN, AZIMUTH_MAX))
    el = np.deg2rad(_clamp(elevation_deg, ELEVATION_MIN, ELEVATION_MAX))
    cos_el = np.cos(el)
    return np.array([
        cos_el * np.cos(az),
        cos_el * np.sin(az),
        np.sin(el),
    ], dtype=np.float32)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _shading_from_luma(luma: np.ndarray, azimuth: float, elevation: float) -> np.ndarray:
    """Approximate a surface-normal field from luma and dot it with the light.

    The returned shading is in roughly ``[-1, 1]`` — negative values
    darken, positive brighten. We don't normalise to ``[0, 1]`` because
    a relight that can darken as well as brighten is more useful.
    """
    gx = _sobel_x(luma)
    gy = _sobel_y(luma)
    # Normalise per-pixel — large magnitudes dominate before normalisation.
    mag = np.sqrt(gx * gx + gy * gy)
    safe_mag = np.where(mag > 1e-3, mag, 1.0)
    nx = gx / safe_mag
    ny = gy / safe_mag
    # The "normal" Z component is what's left after (nx, ny). We assume
    # surfaces face the camera by default (nz = 1) and lean according to
    # gradient magnitude.
    nz = np.maximum(0.0, 1.0 - mag)

    light = light_direction(azimuth, elevation)
    shading = nx * light[0] + ny * light[1] + nz * light[2]
    # Soft-clip into [-1, 1] so very large gradients don't blow out.
    return np.tanh(shading)


def _apply_temperature_shift(
    rgb: np.ndarray, temperature: int, shading: np.ndarray,
) -> np.ndarray:
    """Bias highlights toward warm (orange) or cool (blue)."""
    temperature = _clamp(temperature, TEMPERATURE_MIN, TEMPERATURE_MAX) / 100.0
    if abs(temperature) < 1e-3:
        return rgb
    weight = np.clip(shading, 0.0, 1.0)[..., None]
    if temperature > 0:
        warm = np.array([0.06, 0.02, -0.04], dtype=np.float32)
        return rgb + temperature * weight * warm
    cool = np.array([-0.04, -0.02, 0.06], dtype=np.float32)
    return rgb + (-temperature) * weight * cool


def _sobel_x(plane: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, 1, mode="edge")
    return (
        -padded[:-2, :-2] - 2 * padded[1:-1, :-2] - padded[2:, :-2]
        + padded[:-2, 2:] + 2 * padded[1:-1, 2:] + padded[2:, 2:]
    )


def _sobel_y(plane: np.ndarray) -> np.ndarray:
    padded = np.pad(plane, 1, mode="edge")
    return (
        -padded[:-2, :-2] - 2 * padded[:-2, 1:-1] - padded[:-2, 2:]
        + padded[2:, :-2] + 2 * padded[2:, 1:-1] + padded[2:, 2:]
    )


def _check_input(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"relight expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
        )


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))
