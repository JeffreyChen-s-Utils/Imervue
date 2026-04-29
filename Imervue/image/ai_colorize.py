"""B&W → colour pipeline with two backends.

* :func:`heuristic_colorize` — fully offline. Maps the grayscale
  luminance through one of several preset palettes (sepia, cool, warm).
  No ML model required, ships with the default dependency set.
* :func:`onnx_colorize` — runs a user-supplied ONNX colourisation model
  (DeOldify / iColoriT / SIGGRAPH-2017 colorful-image-colorization).
  Both ``onnxruntime`` and a model file are required.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("Imervue.ai_colorize")


# Preset palettes — each is a list of (luminance position 0..1, [R, G, B]).
HEURISTIC_PRESETS: dict[str, list[tuple[float, list[int]]]] = {
    "sepia": [
        (0.0, [60, 30, 10]),
        (0.5, [180, 130, 70]),
        (1.0, [255, 230, 200]),
    ],
    "cool": [
        (0.0, [10, 20, 60]),
        (0.5, [40, 100, 160]),
        (1.0, [220, 240, 255]),
    ],
    "warm": [
        (0.0, [30, 10, 0]),
        (0.5, [200, 120, 60]),
        (1.0, [255, 220, 180]),
    ],
    "vintage": [
        (0.0, [40, 30, 30]),
        (0.4, [120, 100, 80]),
        (0.7, [200, 170, 120]),
        (1.0, [240, 220, 190]),
    ],
}


@dataclass(frozen=True)
class ColorizeOptions:
    """Knobs shared between the heuristic and ONNX paths."""

    method: str = "sepia"   # heuristic preset name OR "onnx:<model_path>"
    intensity: float = 1.0  # blend with the grayscale source


def heuristic_colorize(
    arr: np.ndarray, options: ColorizeOptions | None = None,
) -> np.ndarray:
    """Map luminance through a preset palette and blend with the original."""
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"heuristic_colorize expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    options = options or ColorizeOptions()
    intensity = max(0.0, min(1.0, float(options.intensity)))
    if intensity <= 0.0:
        return arr

    palette = HEURISTIC_PRESETS.get(options.method, HEURISTIC_PRESETS["sepia"])
    lut = _build_lut(palette)
    luma = (
        0.2126 * arr[..., 0]
        + 0.7152 * arr[..., 1]
        + 0.0722 * arr[..., 2]
    ).astype(np.uint8)
    coloured = lut[luma]

    if intensity >= 1.0 - 1e-6:
        out_rgb = coloured
    else:
        rgb = arr[..., :3].astype(np.float32)
        coloured_f = coloured.astype(np.float32)
        out_rgb = np.clip(
            rgb * (1.0 - intensity) + coloured_f * intensity, 0, 255,
        ).astype(np.uint8)

    out = arr.copy()
    out[..., :3] = out_rgb
    return out


def onnx_colorize(
    arr: np.ndarray, model_path: str, intensity: float = 1.0,
) -> np.ndarray:
    """Run an ONNX colourisation model on ``arr``.

    The model must accept ``(1, 1, H, W)`` luminance float32 in [0, 1]
    and return ``(1, 2, H, W)`` ab-channel deltas in CIELAB-like space,
    OR ``(1, 3, H, W)`` full RGB if the model produces colour directly.
    """
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"onnx_colorize expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}"
        )
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError(
            "onnxruntime is required for the AI colorization model path."
        ) from exc

    session = ort.InferenceSession(
        str(model_path), providers=ort.get_available_providers(),
    )
    input_name = session.get_inputs()[0].name
    luma = (
        0.2126 * arr[..., 0]
        + 0.7152 * arr[..., 1]
        + 0.0722 * arr[..., 2]
    ).astype(np.float32) / 255.0
    tensor = luma[None, None, ...]
    output = session.run(None, {input_name: tensor})[0]
    rgb = _decode_model_output(output, luma)

    intensity = max(0.0, min(1.0, float(intensity)))
    if intensity < 1.0:
        rgb_orig = arr[..., :3].astype(np.float32) / 255.0
        rgb = rgb_orig * (1.0 - intensity) + rgb * intensity
    out = arr.copy()
    out[..., :3] = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    return out


def _decode_model_output(output: np.ndarray, luma: np.ndarray) -> np.ndarray:
    """Convert the model's output tensor to an HxWx3 RGB float in [0, 1]."""
    if output.ndim != 4 or output.shape[0] != 1:
        raise ValueError(f"unexpected model output shape: {output.shape}")
    if output.shape[1] == 3:
        # NCHW → HWC, full RGB output
        return np.clip(np.transpose(output[0], (1, 2, 0)), 0.0, 1.0)
    if output.shape[1] == 2:
        # ab-channel output. The proper conversion is Lab → RGB; without
        # scikit-image we approximate by treating the deltas as a tint
        # that biases the luminance. Documented as approximate so power
        # users can swap in a Lab-aware decoder.
        ab = np.transpose(output[0], (1, 2, 0))
        rgb = np.stack([
            np.clip(luma + 0.4 * ab[..., 0], 0.0, 1.0),
            np.clip(luma - 0.2 * ab[..., 0] - 0.2 * ab[..., 1], 0.0, 1.0),
            np.clip(luma + 0.4 * ab[..., 1], 0.0, 1.0),
        ], axis=-1)
        return rgb
    raise ValueError(
        f"unsupported colourise model output channels: {output.shape[1]}"
    )


def _build_lut(palette: list[tuple[float, list[int]]]) -> np.ndarray:
    """Pre-compute a 256×3 uint8 LUT from a preset palette."""
    positions = np.array([p[0] for p in palette], dtype=np.float32)
    colours = np.array([p[1] for p in palette], dtype=np.float32)
    indices = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    lut = np.zeros((256, 3), dtype=np.float32)
    for ch in range(3):
        lut[:, ch] = np.interp(indices, positions, colours[:, ch])
    return np.clip(lut + 0.5, 0, 255).astype(np.uint8)
