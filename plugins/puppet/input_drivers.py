"""Pure-Python input mappers for the Phase 9 polish features:

* :func:`cursor_to_angle_params` — cursor offset (image pixels) →
  ``ParamAngleX`` / ``ParamAngleY`` value pair
* :func:`blink_curve_value` — time-based open/close cycle for an eye
  parameter
* :func:`audio_rms_to_mouth` — turn an audio buffer's RMS into a
  ``ParamMouthOpenY`` value

No Qt, no sounddevice — those are wired by the canvas / workspace and
gracefully degrade when optional deps are missing.
"""
from __future__ import annotations

import math

import numpy as np

DEFAULT_DRAG_X_PARAM: str = "ParamAngleX"
DEFAULT_DRAG_Y_PARAM: str = "ParamAngleY"
DEFAULT_EYE_PARAMS: tuple[str, str] = ("ParamEyeLOpen", "ParamEyeROpen")
DEFAULT_MOUTH_PARAM: str = "ParamMouthOpenY"

_DEFAULT_BLINK_INTERVAL: float = 4.5   # seconds between blinks (mean)
_DEFAULT_BLINK_DURATION: float = 0.18   # seconds per close+open cycle


def cursor_to_angle_params(
    cursor_x: float,
    cursor_y: float,
    canvas_w: float,
    canvas_h: float,
    *,
    sensitivity: float = 1.0,
) -> dict[str, float]:
    """Map a cursor position (image-space pixels) to angle parameter
    values in ``[-1, 1]`` centred on the canvas midpoint.

    ``sensitivity`` (1.0 default) scales how aggressively the puppet
    follows — values >1 amplify motion, <1 dampen.
    """
    if canvas_w <= 0 or canvas_h <= 0:
        return {DEFAULT_DRAG_X_PARAM: 0.0, DEFAULT_DRAG_Y_PARAM: 0.0}
    nx = (cursor_x - canvas_w * 0.5) / (canvas_w * 0.5)
    ny = (cursor_y - canvas_h * 0.5) / (canvas_h * 0.5)
    nx = max(-1.0, min(1.0, nx * sensitivity))
    ny = max(-1.0, min(1.0, ny * sensitivity))
    return {
        DEFAULT_DRAG_X_PARAM: nx,
        DEFAULT_DRAG_Y_PARAM: ny,
    }


def blink_curve_value(
    elapsed_sec: float,
    *,
    interval: float = _DEFAULT_BLINK_INTERVAL,
    duration: float = _DEFAULT_BLINK_DURATION,
) -> float:
    """Return an eye-open value in ``[0, 1]`` for a continuous blink
    cycle of period ``interval``, where each blink takes ``duration``
    seconds to close + reopen.

    Curve: cosine-shaped close/open inside the blink window so the
    transition feels organic; eye stays fully open the rest of the
    cycle. Identical for both eyes — the canvas hooks the result onto
    L and R parameters in lock-step.
    """
    if interval <= 0 or duration <= 0:
        return 1.0
    phase = elapsed_sec % interval
    if phase >= duration:
        return 1.0
    # Cosine close→open: 1 (open) → 0 (closed) → 1 (open) across the duration.
    u = phase / duration
    return float(0.5 * (1.0 + math.cos(2.0 * math.pi * u)))


def audio_rms_to_mouth(
    samples: np.ndarray | bytes,
    *,
    floor: float = 0.005,
    ceiling: float = 0.2,
) -> float:
    """Compute RMS of ``samples`` and map it to a mouth-open value
    in ``[0, 1]``.

    Below ``floor`` the mouth stays closed; above ``ceiling`` it
    saturates at fully open. The midrange is a linear ramp.

    ``samples`` may be a float32 / int16 numpy array OR raw bytes
    from ``sounddevice``; we normalise to float32 internally.
    """
    arr = _to_float32(samples)
    if arr.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(arr))))
    if rms <= floor:
        return 0.0
    if rms >= ceiling:
        return 1.0
    return (rms - floor) / max(ceiling - floor, 1e-9)


def _to_float32(samples: np.ndarray | bytes) -> np.ndarray:
    if isinstance(samples, bytes):
        # Default to int16 frames since that's what stdlib audio emits.
        arr = np.frombuffer(samples, dtype=np.int16).astype(np.float32) / 32768.0
        return arr
    arr = np.asarray(samples)
    if arr.dtype == np.int16:
        return arr.astype(np.float32) / 32768.0
    if arr.dtype != np.float32:
        return arr.astype(np.float32)
    return arr
