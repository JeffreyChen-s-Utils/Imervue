"""Segment-Anything (SAM) point-prompt masking via ONNX.

SAM ships as two ONNX graphs: a heavy image **encoder** (image → embeddings)
and a light **decoder** (embeddings + click points → mask). Drop both into
``plugins/ai_object_remove/models/`` (filenames containing ``encoder`` /
``decoder``) and the Remove Object dialog offers a precise point-select mask
that feeds the existing inpainter.

The pre/post-processing (resize-longest-side, normalisation, point prompt
arrays, logit thresholding) is pure NumPy and unit-tested. The ``onnxruntime``
inference itself is optional and model-specific, so it degrades gracefully when
the package or models are absent.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

SAM_TARGET = 1024
_MASK_INPUT_SIZE = 256
_PIXEL_MEAN = (123.675, 116.28, 103.53)
_PIXEL_STD = (58.395, 57.12, 57.375)
_RGB_CHANNELS = 3
_PADDING_LABEL = -1.0


def longest_side_scale(h: int, w: int, target: int = SAM_TARGET) -> float:
    """Scale factor that maps the longest side of an image to *target*."""
    longest = max(h, w)
    return target / longest if longest > 0 else 1.0


def resized_hw(h: int, w: int, target: int = SAM_TARGET) -> tuple[int, int]:
    """Resized ``(height, width)`` with the longest side at *target*."""
    scale = longest_side_scale(h, w, target)
    return round(h * scale), round(w * scale)


def preprocess_point_coords(
    points: list[tuple[float, float]], scale: float,
) -> np.ndarray:
    """Scale click points to the resized frame and append SAM's padding point."""
    coords = [[x * scale, y * scale] for x, y in points]
    coords.append([0.0, 0.0])
    return np.array([coords], dtype=np.float32)


def preprocess_point_labels(labels: list[int]) -> np.ndarray:
    """Append the padding label (-1) SAM expects after the real point labels."""
    return np.array([[*[float(v) for v in labels], _PADDING_LABEL]], dtype=np.float32)


def normalize_image(resized_rgb: np.ndarray, target: int = SAM_TARGET) -> np.ndarray:
    """Mean/std-normalise a resized RGB image and pad to ``1x3xTxT`` NCHW."""
    arr = (resized_rgb.astype(np.float32)
           - np.array(_PIXEL_MEAN, dtype=np.float32)) / np.array(_PIXEL_STD, dtype=np.float32)
    h, w = arr.shape[:2]
    padded = np.zeros((target, target, _RGB_CHANNELS), dtype=np.float32)
    padded[:h, :w] = arr
    return np.transpose(padded, (2, 0, 1))[None, ...]


def binarize_mask(logits: np.ndarray, threshold: float = 0.0) -> np.ndarray:
    """Reduce a SAM mask-logits tensor to a single ``HxW`` boolean mask."""
    arr = np.asarray(logits)
    while arr.ndim > 2:
        arr = arr[0]
    return arr > threshold


def discover_sam_models(models_dir: str | Path) -> tuple[str | None, str | None]:
    """Find the SAM encoder/decoder ONNX files in *models_dir* by filename."""
    directory = Path(models_dir)
    if not directory.is_dir():
        return None, None
    encoder = decoder = None
    for onnx in sorted(directory.glob("*.onnx")):
        name = onnx.name.lower()
        if "encoder" in name and encoder is None:
            encoder = str(onnx)
        elif "decoder" in name and decoder is None:
            decoder = str(onnx)
    return encoder, decoder


def sam_mask(arr: np.ndarray, points: list[tuple[float, float]], labels: list[int],
             encoder_path: str, decoder_path: str) -> np.ndarray:
    """Run SAM with foreground click *points* and return a boolean ``HxW`` mask.

    ``onnxruntime`` is optional; its absence raises ``ImportError`` so the dialog
    can fall back to flood-fill.
    """
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] < _RGB_CHANNELS:
        raise ValueError(f"expected HxWxC (C>=3) image, got {arr.shape}")
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError("onnxruntime is required for SAM masking.") from exc
    from PIL import Image

    h, w = arr.shape[:2]
    scale = longest_side_scale(h, w)
    new_h, new_w = resized_hw(h, w)
    resized = np.asarray(
        Image.fromarray(arr[..., :_RGB_CHANNELS]).resize(
            (new_w, new_h), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    providers = ort.get_available_providers()
    encoder = ort.InferenceSession(str(encoder_path), providers=providers)
    embeddings = encoder.run(
        None, {encoder.get_inputs()[0].name: normalize_image(resized)},
    )[0]
    decoder = ort.InferenceSession(str(decoder_path), providers=providers)
    feed = {
        "image_embeddings": embeddings,
        "point_coords": preprocess_point_coords(points, scale),
        "point_labels": preprocess_point_labels(labels),
        "mask_input": np.zeros((1, 1, _MASK_INPUT_SIZE, _MASK_INPUT_SIZE), dtype=np.float32),
        "has_mask_input": np.zeros(1, dtype=np.float32),
        "orig_im_size": np.array([h, w], dtype=np.float32),
    }
    return binarize_mask(decoder.run(None, feed)[0])
