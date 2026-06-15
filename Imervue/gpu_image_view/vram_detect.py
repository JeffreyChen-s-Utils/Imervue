"""GL-driver VRAM detection for the tile-cache budget.

Orchestrates the user-override check and the vendor GL probes, then sets
``view._vram_limit``. The pure clamp / override policy lives in
:mod:`Imervue.gpu_image_view.vram_budget`; this module is the GL-touching
glue (``glGetIntegerv`` / ``glGetError``) and is therefore covered by
``# pragma: no cover`` on the probe paths.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from OpenGL.GL import GL_NO_ERROR, glGetError, glGetIntegerv

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_LOG = logging.getLogger("Imervue.vram")

# Vendor GL enums for total/free VRAM (KB).
_NVX_TOTAL_AVAILABLE = 0x9048  # NVIDIA GPU_MEMORY_INFO_TOTAL_AVAILABLE_MEMORY_NVX
_ATI_TEXTURE_FREE = 0x87FC  # AMD TEXTURE_FREE_MEMORY_ATI (4-int vector)
_BYTES_PER_MB = 1024 * 1024
_DETECTED_FRACTION = 0.4


def detect_vram_limit(view: GPUImageView) -> None:
    """Size ``view._vram_limit`` to real VRAM, or keep the safe default.

    A user override (Preferences > VRAM limit) takes precedence — if
    ``vram_limit_auto`` is ``False`` the user's value is used as-is and no
    driver probing happens. Otherwise the detected total is clamped to
    ``[256 MB, 8 GB]`` so a bad query can't blow up memory or disable the
    cache.
    """
    if _apply_user_override(view):
        return

    total_kb = _probe_vendor_vram_kb()
    _drain_gl_error_queue()

    if total_kb <= 0:
        _LOG.info(
            "VRAM detection not supported on this driver, using default %d MB",
            view._vram_limit_default // _BYTES_PER_MB,
        )
        return

    from Imervue.gpu_image_view.vram_budget import clamp_detected_bytes
    total_bytes = total_kb * 1024
    detected = clamp_detected_bytes(int(total_bytes * _DETECTED_FRACTION))
    view._vram_limit = detected
    _LOG.info(
        "Detected VRAM %d MB → tile cache limit set to %d MB",
        total_bytes // _BYTES_PER_MB, detected // _BYTES_PER_MB,
    )


def _apply_user_override(view: GPUImageView) -> bool:
    """Apply a user-configured VRAM limit, returning True when honoured."""
    from Imervue.gpu_image_view.vram_budget import compute_user_override_bytes
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    override = compute_user_override_bytes(user_setting_dict)
    if override is None:
        return False
    view._vram_limit = override
    _LOG.info(
        "User-configured VRAM tile cache limit: %d MB", override // _BYTES_PER_MB,
    )
    return True


def _probe_vendor_vram_kb() -> int:  # pragma: no cover - GL probe path
    """Try NVX (NVIDIA) then ATI (AMD) VRAM probes, return KB or 0."""
    kb = _probe_gl_integer(_NVX_TOTAL_AVAILABLE)
    if kb > 0:
        return kb
    # AMD: 4-int vector, take total free pool (first element).
    return _probe_gl_integer(_ATI_TEXTURE_FREE)


def _probe_gl_integer(enum: int) -> int:  # pragma: no cover - GL probe path
    """Read an integer (or first element of a vector) from glGetIntegerv."""
    try:
        val = glGetIntegerv(enum)
    except Exception:  # noqa: BLE001 - any GL failure means "unsupported"
        return 0
    if isinstance(val, (list, tuple)):
        return int(val[0]) if val else 0
    return int(val) if val is not None else 0


def _drain_gl_error_queue() -> None:  # pragma: no cover - GL probe path
    """Clear any GL error left by extension probes that aren't supported."""
    with contextlib.suppress(Exception):
        # glGetError has the side-effect of clearing the flag.
        while glGetError() != GL_NO_ERROR:  # noqa: S108
            continue
