"""VRAM budget resolution for the GPU tile cache.

Pure-Python helper extracted from ``GPUImageView`` so the budget logic is
unit-testable without a live OpenGL context. Two pieces:

* :func:`compute_user_override_bytes` — checks ``user_setting_dict`` for an
  explicit limit and returns it (in bytes) when set, else ``None``.
* :func:`clamp_detected_bytes` — applies the safety floor / ceiling to a
  driver-reported value so a bad probe can't misconfigure the cache.

The auto-detection probe itself stays in ``GPUImageView`` because it needs
the live GL context, but the value it produces flows through these helpers.
"""
from __future__ import annotations

VRAM_MIN_MB = 256
VRAM_MAX_MB = 8192
VRAM_DEFAULT_MB = 1536  # 1.5 GB conservative fallback


def compute_user_override_bytes(settings: dict) -> int | None:
    """Return the user-configured tile-cache limit in bytes, or ``None``.

    Returns ``None`` when ``vram_limit_auto`` is truthy (the caller should
    fall back to driver auto-detect) or when the configured value can't be
    parsed as an integer. Values outside the safe ``[256, 8192]`` MB range
    are clamped — never silently dropped — so a typo can't disable the cache.
    """
    if settings.get("vram_limit_auto", True):
        return None
    try:
        requested_mb = int(settings.get("vram_limit_mb", VRAM_DEFAULT_MB))
    except (TypeError, ValueError):
        return None
    clamped_mb = max(VRAM_MIN_MB, min(VRAM_MAX_MB, requested_mb))
    return clamped_mb * 1024 * 1024


def clamp_detected_bytes(detected_bytes: int) -> int:
    """Clamp a driver-reported byte count to the safe budget range."""
    min_bytes = VRAM_MIN_MB * 1024 * 1024
    max_bytes = VRAM_MAX_MB * 1024 * 1024
    return max(min_bytes, min(max_bytes, int(detected_bytes)))
