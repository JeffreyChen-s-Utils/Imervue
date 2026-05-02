"""Motion-deblur algorithms: Wiener deconvolution + optional ONNX inference.

Two paths share the same dialog:

* :func:`wiener_deblur` — frequency-domain Wiener deconvolution using a
  caller-supplied PSF (Gaussian or directional motion line). Pure numpy,
  ships with the default deps. Best suited to mild blur where the PSF is
  approximately known.
* :func:`onnx_deblur` — loads a user-supplied DeblurGAN / MIMO-UNet
  ONNX model from ``plugins/ai_motion_deblur/models/`` and runs it via
  ``onnxruntime``. The plugin does not bundle weights — the user drops
  a model in.

Both return ``HxWx4 uint8`` arrays. Alpha is preserved unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

PSF_GAUSSIAN_RADIUS_MIN = 1
PSF_GAUSSIAN_RADIUS_MAX = 25
PSF_MOTION_LENGTH_MIN = 3
PSF_MOTION_LENGTH_MAX = 60
PSF_ANGLE_MIN = 0
PSF_ANGLE_MAX = 180
SNR_DB_MIN = 5
SNR_DB_MAX = 60
BLEND_MIN = 0.0
BLEND_MAX = 1.0


@dataclass(frozen=True)
class WienerOptions:
    """Tuning for :func:`wiener_deblur`."""

    psf_kind: str = "gaussian"        # "gaussian" or "motion"
    gaussian_radius: int = 3
    motion_length: int = 15
    motion_angle: int = 0             # degrees, 0 = horizontal
    snr_db: int = 25                  # noise-to-signal ratio in decibels
    blend: float = 1.0                # mix with original (1.0 = full deblur)


def wiener_deblur(arr: np.ndarray, options: WienerOptions | None = None) -> np.ndarray:
    """Apply Wiener deconvolution to each colour channel."""
    _check_input(arr)
    options = options or WienerOptions()
    blend = max(BLEND_MIN, min(BLEND_MAX, float(options.blend)))
    if blend <= 0.0:
        return arr.copy()

    psf = _build_psf(options)
    snr = 10.0 ** (max(SNR_DB_MIN, min(SNR_DB_MAX, options.snr_db)) / 10.0)

    rgb = arr[..., :3].astype(np.float32) / 255.0
    deblurred = np.empty_like(rgb)
    for c in range(3):
        deblurred[..., c] = _wiener_channel(rgb[..., c], psf, snr)

    deblurred = np.clip(deblurred * 255.0, 0.0, 255.0)
    if blend < 1.0:
        deblurred = arr[..., :3].astype(np.float32) * (1.0 - blend) + deblurred * blend
    out = np.empty_like(arr)
    out[..., :3] = deblurred.astype(np.uint8)
    out[..., 3] = arr[..., 3]
    return out


def onnx_deblur(arr: np.ndarray, model_path: str | Path, *, blend: float = 1.0) -> np.ndarray:
    """Run a user-supplied ONNX deblur model.

    Expects the model's first input to be NCHW float32 in ``[0, 1]`` and
    its first output to match. Common DeblurGAN / MIMO-UNet exports use
    that layout. Models that need preprocessing beyond ``/255.0`` are
    not supported; users with a different model should re-export.
    """
    _check_input(arr)
    blend = max(BLEND_MIN, min(BLEND_MAX, float(blend)))
    if blend <= 0.0:
        return arr.copy()

    import onnxruntime as ort  # heavy optional dep

    session = ort.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"],
    )
    rgb = arr[..., :3].astype(np.float32) / 255.0
    nchw = rgb.transpose(2, 0, 1)[None, ...]
    input_name = session.get_inputs()[0].name
    out_nchw = session.run(None, {input_name: nchw})[0]

    if out_nchw.ndim == 4:
        out_chw = out_nchw[0]
    elif out_nchw.ndim == 3:
        out_chw = out_nchw
    else:
        raise ValueError(
            f"ONNX deblur model returned unexpected rank {out_nchw.ndim}",
        )
    out_rgb = np.clip(out_chw.transpose(1, 2, 0), 0.0, 1.0) * 255.0

    out = np.empty_like(arr)
    if blend < 1.0:
        out[..., :3] = (
            arr[..., :3].astype(np.float32) * (1.0 - blend)
            + out_rgb * blend
        ).astype(np.uint8)
    else:
        out[..., :3] = out_rgb.astype(np.uint8)
    out[..., 3] = arr[..., 3]
    return out


def gaussian_psf(radius: int) -> np.ndarray:
    """Return a normalised 2D Gaussian PSF of the given radius."""
    radius = max(PSF_GAUSSIAN_RADIUS_MIN, min(PSF_GAUSSIAN_RADIUS_MAX, int(radius)))
    size = 2 * radius + 1
    sigma = radius / 2.0 if radius > 0 else 0.5
    yy, xx = np.indices((size, size), dtype=np.float32)
    cy = cx = radius
    psf = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma * sigma))
    return psf / psf.sum()


def motion_psf(length: int, angle_degrees: int) -> np.ndarray:
    """Return a normalised line PSF of given length / angle (degrees)."""
    length = max(PSF_MOTION_LENGTH_MIN, min(PSF_MOTION_LENGTH_MAX, int(length)))
    angle = float(max(PSF_ANGLE_MIN, min(PSF_ANGLE_MAX, int(angle_degrees))))
    radians = np.deg2rad(angle)
    half = length // 2
    size = 2 * half + 1
    psf = np.zeros((size, size), dtype=np.float32)
    cos_a = np.cos(radians)
    sin_a = np.sin(radians)
    for t in np.linspace(-half, half, length):
        x = int(round(half + t * cos_a))
        y = int(round(half + t * sin_a))
        if 0 <= x < size and 0 <= y < size:
            psf[y, x] = 1.0
    total = psf.sum()
    if total <= 0:
        psf[half, half] = 1.0
        return psf
    return psf / total


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_psf(options: WienerOptions) -> np.ndarray:
    if options.psf_kind == "gaussian":
        return gaussian_psf(options.gaussian_radius)
    if options.psf_kind == "motion":
        return motion_psf(options.motion_length, options.motion_angle)
    raise ValueError(f"unknown psf_kind {options.psf_kind!r}")


def _wiener_channel(channel: np.ndarray, psf: np.ndarray, snr: float) -> np.ndarray:
    """One-channel Wiener deconvolution in the frequency domain."""
    h, w = channel.shape
    psf_padded = np.zeros_like(channel)
    ph, pw = psf.shape
    psf_padded[:ph, :pw] = psf
    # Centre the PSF so the output is not shifted.
    psf_padded = np.roll(psf_padded, -(ph // 2), axis=0)
    psf_padded = np.roll(psf_padded, -(pw // 2), axis=1)

    g = np.fft.rfft2(channel)
    h_f = np.fft.rfft2(psf_padded)
    denom = (np.abs(h_f) ** 2) + (1.0 / snr)
    f_hat = (np.conj(h_f) / denom) * g
    return np.fft.irfft2(f_hat, s=(h, w))


def _check_input(arr: np.ndarray) -> None:
    if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
        raise ValueError(
            f"deblur expects HxWx4 uint8 RGBA, got {arr.shape} {arr.dtype}",
        )
