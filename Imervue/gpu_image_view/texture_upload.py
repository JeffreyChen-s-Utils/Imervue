"""Unified RGBA texture-upload helpers.

Three call sites used to hand-roll the same ``glGenTextures`` +
``glTexImage2D`` + four ``glTexParameteri`` dance, plus the
``RGB → RGBA`` alpha padding via ``np.concatenate``. This module
collapses that duplication into:

* :func:`prepare_rgba` — pure, GL-free data preparation (alpha
  padding, ``uint8`` coercion, C-contiguity). Fully unit-testable
  without a live GL context.
* :func:`upload_rgba_texture` — the GL upload itself. Guarded by
  ``# pragma: no cover`` because it needs a live context, but its
  decision inputs (filter / mipmap flags) come from pure callers.

The pixel-buffer-object (PBO) streaming path is wired through
:class:`Imervue.gpu_image_view.pbo_uploader.PBOTextureUploader`;
:func:`upload_rgba_texture` accepts an optional uploader and uses
``decide_upload_path`` to gate the async path, always falling back
to the synchronous ``glTexImage2D`` when the PBO is unavailable.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.pbo_uploader import PBOTextureUploader

_ALPHA_OPAQUE: int = 255
_RGB_CHANNELS: int = 3
_RGBA_CHANNELS: int = 4


def prepare_rgba(arr: np.ndarray) -> np.ndarray:
    """Return *arr* as a C-contiguous ``uint8`` RGBA array.

    Behaviour (matches the three legacy call sites it replaces):

    * 2-D (grayscale / single channel) → broadcast to RGB, then
      pad an opaque alpha channel.
    * 3-channel RGB → pad an opaque alpha channel.
    * 4-channel RGBA → passed through unchanged (besides dtype /
      contiguity normalisation).

    The result is always ``uint8`` and C-contiguous so it can be
    handed straight to ``glTexImage2D`` without the driver reading
    off the end of a strided buffer.
    """
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)

    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=2)

    channels = arr.shape[2]
    if channels == _RGB_CHANNELS:
        alpha = np.full((*arr.shape[:2], 1), _ALPHA_OPAQUE, dtype=np.uint8)
        arr = np.concatenate([arr, alpha], axis=2)
    elif channels != _RGBA_CHANNELS:
        raise ValueError(
            f"prepare_rgba expects 1/3/4 channels, got {channels}"
        )

    if not arr.flags["C_CONTIGUOUS"]:
        arr = np.ascontiguousarray(arr)
    return arr


def upload_rgba_texture(
    rgba: np.ndarray,
    *,
    generate_mipmaps: bool = False,
    clamp_to_edge: bool = True,
    uploader: PBOTextureUploader | None = None,
) -> int:   # pragma: no cover - needs a live GL context
    """Create a GL texture from an already-prepared RGBA array.

    *rgba* MUST already be C-contiguous ``uint8`` RGBA — call
    :func:`prepare_rgba` first. Returns the new texture handle.

    ``generate_mipmaps`` builds the full mip chain and selects the
    trilinear minification filter (used by the deep-zoom tile path);
    otherwise a plain ``GL_LINEAR`` minification filter is used
    (minimap / wall thumbnails).

    When *uploader* is supplied and
    :meth:`PBOTextureUploader.decide_upload_path` selects ``"pbo"``,
    the pixel data streams through the PBO ring; otherwise the
    synchronous ``glTexImage2D`` path runs. The render result is
    identical either way — the PBO only changes *how* the bytes
    reach the driver, not the texture contents.
    """
    from OpenGL.GL import (
        GL_CLAMP_TO_EDGE,
        GL_LINEAR,
        GL_LINEAR_MIPMAP_LINEAR,
        GL_RGBA,
        GL_TEXTURE_2D,
        GL_TEXTURE_MAG_FILTER,
        GL_TEXTURE_MIN_FILTER,
        GL_TEXTURE_WRAP_S,
        GL_TEXTURE_WRAP_T,
        GL_UNPACK_ALIGNMENT,
        GL_UNSIGNED_BYTE,
        glBindTexture,
        glGenerateMipmap,
        glGenTextures,
        glPixelStorei,
        glTexImage2D,
        glTexParameteri,
    )

    height, width = rgba.shape[0], rgba.shape[1]
    tex = int(glGenTextures(1))
    glBindTexture(GL_TEXTURE_2D, tex)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

    used_pbo = _try_pbo_upload(uploader, tex, rgba, width, height)
    if not used_pbo:
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
            GL_RGBA, GL_UNSIGNED_BYTE, rgba,
        )

    if generate_mipmaps:
        glGenerateMipmap(GL_TEXTURE_2D)
        min_filter = GL_LINEAR_MIPMAP_LINEAR
    else:
        min_filter = GL_LINEAR

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, min_filter)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    if clamp_to_edge:
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    return tex


def _try_pbo_upload(
    uploader: PBOTextureUploader | None,
    tex: int,
    rgba: np.ndarray,
    width: int,
    height: int,
) -> bool:   # pragma: no cover - needs a live GL context
    """Attempt a PBO streaming upload into the already-bound *tex*.

    Returns ``True`` when the PBO path ran (so the caller skips the
    synchronous ``glTexImage2D``), ``False`` to fall back. Any GL
    surface failure falls back silently — correctness over speed.
    """
    if uploader is None:
        return False
    from Imervue.gpu_image_view.pbo_uploader import PBOTextureUploader

    path = PBOTextureUploader.decide_upload_path(
        width, height, initialised=uploader.initialised,
    )
    if path != "pbo":
        return False
    return uploader.stream_upload(tex, rgba, width, height)
