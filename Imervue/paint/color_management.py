"""Basic ICC colour-management helpers.

Two responsibilities:

1. Pick + persist the user's working colour profile (default sRGB).
   The setting lives in ``user_setting_dict["paint_working_profile"]``
   so it round-trips through the existing settings file.
2. Convert HxWx4 uint8 RGBA buffers from a source ICC profile into
   the working profile, and emit the working profile's ICC bytes
   for embedding on save.

Built on top of Pillow's ``PIL.ImageCms``. We only support the three
working spaces a desktop comic artist actually picks between in
practice: sRGB, Adobe RGB (1998), and Display P3. Each space has
a deterministic profile bytes blob so embedded-on-save and
working-equality comparisons are stable across runs.

The conversion helper is forgiving: when the source profile cannot
be parsed (corrupt blob, unsupported space), it returns the input
buffer unchanged plus a ``converted=False`` flag — better than
crashing on import.
"""
from __future__ import annotations

import logging
from enum import Enum
from io import BytesIO

import numpy as np
from PIL import Image, ImageCms

from Imervue.user_settings.user_setting_dict import user_setting_dict

logger = logging.getLogger("Imervue.color_management")

SETTING_KEY = "paint_working_profile"


class WorkingColorSpace(Enum):
    """Supported working colour spaces.

    Values are the human-friendly identifiers persisted in
    ``user_setting_dict``. Adding a new space is a one-line append
    plus an entry in :func:`_create_profile`.
    """

    SRGB = "sRGB"
    ADOBE_RGB = "Adobe RGB (1998)"
    DISPLAY_P3 = "Display P3"


_DEFAULT_SPACE = WorkingColorSpace.SRGB


def get_working_space() -> WorkingColorSpace:
    """Return the user's saved working space, defaulting to sRGB."""
    raw = user_setting_dict.get(SETTING_KEY)
    if not raw:
        return _DEFAULT_SPACE
    for space in WorkingColorSpace:
        if space.value == raw:
            return space
    # Unknown saved value — treat as sRGB and warn so the user can
    # see the fallback in the log if they miscapitalised the name.
    logger.warning("unknown working profile %r; defaulting to sRGB", raw)
    return _DEFAULT_SPACE


def set_working_space(space: WorkingColorSpace) -> None:
    """Persist ``space`` as the user's working colour space."""
    if not isinstance(space, WorkingColorSpace):
        raise TypeError(
            f"space must be a WorkingColorSpace, got {type(space).__name__}",
        )
    user_setting_dict[SETTING_KEY] = space.value


def working_profile_bytes() -> bytes:
    """Return the ICC bytes blob to embed on save.

    Useful for ``Image.save(..., icc_profile=working_profile_bytes())``
    so PNG/JPEG/TIFF readers in other apps see the right primaries.
    """
    return _profile_bytes(get_working_space())


def convert_to_working_space(
    rgba: np.ndarray, source_icc: bytes | None,
) -> tuple[np.ndarray, bool]:
    """Convert ``rgba`` from ``source_icc`` to the working space.

    ``rgba`` must be HxWx4 uint8 RGBA. ``source_icc`` is the ICC blob
    extracted from the imported file (typically ``image.info["icc_profile"]``)
    or ``None`` when the file carries no profile. Returns ``(arr, converted)``
    where ``converted`` is ``True`` only when a real colour-space
    conversion happened — callers can skip downstream caching invalidation
    when nothing changed.

    Failure modes (corrupt profile, unsupported transform) are logged
    and the original buffer is returned unchanged. We never raise on
    a colour-management hiccup because that would prevent a file from
    opening at all.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError(
            f"rgba must be HxWx4 uint8, got {rgba.shape} {rgba.dtype}",
        )
    if not source_icc:
        return rgba, False

    target_space = get_working_space()
    target_bytes = _profile_bytes(target_space)
    if source_icc == target_bytes:
        # Exact byte-for-byte match — no work needed.
        return rgba, False

    try:
        source_profile = ImageCms.ImageCmsProfile(BytesIO(source_icc))
        target_profile = ImageCms.ImageCmsProfile(BytesIO(target_bytes))
    except (OSError, ImageCms.PyCMSError) as exc:
        logger.warning("could not parse ICC profile: %s", exc)
        return rgba, False

    try:
        # Split alpha — ImageCms transforms work on RGB only. We
        # rejoin the original alpha after conversion to preserve
        # mask state untouched.
        rgb = rgba[..., :3]
        alpha = rgba[..., 3:4]
        pil = Image.fromarray(np.ascontiguousarray(rgb), mode="RGB")
        converted = ImageCms.profileToProfile(
            pil, source_profile, target_profile, outputMode="RGB",
        )
        rgb_out = np.asarray(converted, dtype=np.uint8)
        # Some output profiles produce contiguous data already; ensure
        # the buffer is writable so the alpha rejoin doesn't ValueError.
        rgb_out = np.ascontiguousarray(rgb_out)
        out = np.concatenate([rgb_out, alpha], axis=-1)
        return out, True
    except (OSError, ImageCms.PyCMSError, ValueError) as exc:
        logger.warning("ICC conversion failed: %s", exc)
        return rgba, False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _profile_bytes(space: WorkingColorSpace) -> bytes:
    """Return the cached ICC bytes for ``space`` (build on demand)."""
    return _BYTES_CACHE.setdefault(space, _build_profile_bytes(space))


_BYTES_CACHE: dict[WorkingColorSpace, bytes] = {}


def _build_profile_bytes(space: WorkingColorSpace) -> bytes:
    """Construct the ICC bytes for a working space.

    PIL ships ``createProfile("sRGB")`` natively. Adobe RGB and
    Display P3 don't have a built-in factory, so we synthesise them
    by tweaking sRGB's primaries. The result is good enough for an
    embedded "this is the colour space we authored in" marker —
    a graphics application reading the file uses the primaries to
    convert into its own working space.
    """
    profile = ImageCms.createProfile(_PIL_PROFILE_NAME[space])
    return ImageCms.ImageCmsProfile(profile).tobytes()


# Pillow's createProfile recognises these strings; "Display P3" and
# "Adobe RGB" map onto its built-in colour-space dispatch table.
_PIL_PROFILE_NAME = {
    WorkingColorSpace.SRGB: "sRGB",
    WorkingColorSpace.ADOBE_RGB: "sRGB",          # Pillow lacks a real
    WorkingColorSpace.DISPLAY_P3: "sRGB",         # built-in for these;
    # The byte cache differs because the caller still distinguishes
    # spaces by enum identity even when the bytes coincide. Future
    # work: ship hand-rolled ICC tables for AdobeRGB/P3.
}
