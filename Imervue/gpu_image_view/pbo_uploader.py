"""Pixel-Buffer-Object texture upload helper.

``glTexImage2D`` with a CPU pointer is *mostly* async on modern
drivers — the driver queues the upload into its command stream
— but the call still pulls the source bytes through the driver's
internal staging copy, which can stall the GUI thread when the
GPU is under pressure (another OpenGL / Vulkan app running, large
batch of tiles arriving at once).

PBOs decouple this: the driver maps a chunk of buffer memory
(potentially DMA-mapped on the GPU side); the CPU writes pixels
into that memory; ``glTexSubImage2D`` reads from the PBO at the
GPU's leisure. The CPU-side write and the GPU-side consume can
overlap with other work.

Two PBOs in round-robin let frame N's CPU write happen while
frame N-1's GPU consume drains — same pattern every "streaming
PBO" tutorial uses.

This module ships the pure round-robin / sizing logic as testable
helpers; the actual GL calls live behind ``# pragma: no cover``
in the wrapper class because exercising them needs a live GL
context.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("Imervue.gpu_image_view.pbo_uploader")

PBO_RING_SIZE: int = 2
"""Two-buffer round-robin. Bigger rings don't help — the bound
limit is "one buffer being filled by CPU, one being consumed by
GPU"; adding more just wastes VRAM."""

DEFAULT_MAX_TILE_SIDE: int = 1024
"""Upper bound for the per-PBO byte allocation. Tiles above this
fall back to direct ``glTexImage2D``; the PBO would have to be
re-allocated each call, defeating the buffer-reuse purpose."""


def next_ring_index(current: int, ring_size: int = PBO_RING_SIZE) -> int:
    """Round-robin successor for the PBO index. Pure function so
    the uploader's index tracking is testable without a GL
    context."""
    if ring_size <= 0:
        return 0
    return (int(current) + 1) % int(ring_size)


def pbo_buffer_bytes(
    max_side: int = DEFAULT_MAX_TILE_SIDE,
    *,
    bytes_per_pixel: int = 4,
) -> int:
    """Per-PBO allocation size: ``max_side² × bpp`` so any tile
    up to ``max_side × max_side`` fits without a re-allocation.

    Robust to non-positive arguments (returns 0; the uploader
    treats that as "PBO disabled, use direct upload")."""
    side = max(0, int(max_side))
    bpp = max(0, int(bytes_per_pixel))
    return side * side * bpp


def tile_fits_pbo(
    width: int, height: int,
    *,
    max_side: int = DEFAULT_MAX_TILE_SIDE,
) -> bool:
    """``True`` when a ``(width × height)`` tile can be uploaded
    through a PBO of the documented buffer size. Out-of-range
    tiles use the direct path."""
    if width <= 0 or height <= 0:
        return False
    return int(width) <= int(max_side) and int(height) <= int(max_side)


class PBOTextureUploader:
    """Wraps the round-robin PBO logic. Construct once per
    canvas; call :meth:`upload` instead of ``glTexImage2D`` and
    the helper picks the best path (PBO when the tile fits and
    the GL context supports it, fall back to direct otherwise).

    The GL calls are guarded by ``# pragma: no cover`` because a
    headless test runner has no live context to exercise them.
    Tests cover the pure index / size helpers and the upload-path
    decision logic via the ``decide_upload_path`` classmethod.
    """

    def __init__(self, *, max_side: int = DEFAULT_MAX_TILE_SIDE) -> None:
        self._max_side = int(max_side)
        self._buffer_bytes = pbo_buffer_bytes(self._max_side)
        self._pbos: list[int] = []
        self._next_index: int = 0
        self._initialised: bool = False

    # ---- public API ------------------------------------------------

    @property
    def initialised(self) -> bool:
        return self._initialised

    @property
    def buffer_bytes(self) -> int:
        return self._buffer_bytes

    def initialise(self) -> bool:   # pragma: no cover - needs GL context
        """Allocate the PBO ring. Returns ``False`` when the GL
        driver refuses (e.g. missing extension on a stripped-down
        embedded GL). The uploader transparently falls back to
        direct upload in that case."""
        if self._initialised:
            return True
        if self._buffer_bytes <= 0:
            return False
        try:
            from OpenGL.GL import (
                GL_PIXEL_UNPACK_BUFFER,
                GL_STREAM_DRAW,
                glBindBuffer,
                glBufferData,
                glGenBuffers,
            )
        except ImportError:
            return False
        try:
            self._pbos = [int(glGenBuffers(1)) for _ in range(PBO_RING_SIZE)]
            for pbo in self._pbos:
                glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
                glBufferData(
                    GL_PIXEL_UNPACK_BUFFER,
                    self._buffer_bytes,
                    None,
                    GL_STREAM_DRAW,
                )
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)
        except Exception as exc:   # noqa: BLE001 - GL error surface varies
            logger.info("PBO initialise failed (%s); fallback to direct upload", exc)
            self._pbos = []
            return False
        self._initialised = True
        return True

    @classmethod
    def decide_upload_path(
        cls,
        width: int,
        height: int,
        *,
        initialised: bool,
        max_side: int = DEFAULT_MAX_TILE_SIDE,
    ) -> str:
        """Return ``"pbo"`` when the uploader should stream through
        a PBO, ``"direct"`` for the fallback path. Pure helper so
        the decision matrix is testable without GL."""
        if not initialised:
            return "direct"
        if not tile_fits_pbo(width, height, max_side=max_side):
            return "direct"
        return "pbo"

    def advance(self) -> int:
        """Bump the round-robin index, return the *previous* value
        so the caller can pick which PBO to bind for this upload.
        Pure bookkeeping — no GL calls."""
        idx = self._next_index
        self._next_index = next_ring_index(idx, PBO_RING_SIZE)
        return idx

    def stream_upload(
        self, tex: int, rgba, width: int, height: int,
    ) -> bool:   # pragma: no cover - needs GL context
        """Stream *rgba* into the already-bound texture *tex* via the
        next PBO in the ring.

        Returns ``True`` when the PBO upload completed, ``False`` to
        let the caller fall back to the synchronous path. The bound
        texture must already be ``glBindTexture``-ed by the caller;
        this method only touches the unpack-buffer binding and
        restores it to 0 before returning.
        """
        if not self._initialised or not self._pbos:
            return False
        try:
            from OpenGL.GL import (
                GL_PIXEL_UNPACK_BUFFER,
                GL_RGBA,
                GL_TEXTURE_2D,
                GL_UNSIGNED_BYTE,
                glBindBuffer,
                glBufferSubData,
                glTexImage2D,
                glTexSubImage2D,
            )
        except ImportError:
            return False
        try:
            data = rgba.tobytes()
            pbo = self._pbos[self.advance()]
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, pbo)
            glBufferSubData(GL_PIXEL_UNPACK_BUFFER, 0, len(data), data)
            # Allocate texture storage, then fill from the bound PBO
            # (the final ``None`` pointer is interpreted as a byte
            # offset into the bound unpack buffer).
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                GL_RGBA, GL_UNSIGNED_BYTE, None,
            )
            glTexSubImage2D(
                GL_TEXTURE_2D, 0, 0, 0, width, height,
                GL_RGBA, GL_UNSIGNED_BYTE, None,
            )
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)
        except Exception as exc:   # noqa: BLE001 - GL error surface varies
            logger.info("PBO stream_upload failed (%s); fallback to direct", exc)
            self._unbind_unpack_buffer()
            return False
        return True

    @staticmethod
    def _unbind_unpack_buffer() -> None:   # pragma: no cover - needs GL context
        """Best-effort restore of the unpack-buffer binding to 0 after a
        failed streaming upload, so the synchronous fallback runs with a
        clean binding."""
        try:
            from OpenGL.GL import GL_PIXEL_UNPACK_BUFFER, glBindBuffer
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0)
        except Exception as exc:   # noqa: BLE001 - GL error surface varies
            logger.info("PBO unbind swallowed: %s", exc)

    def shutdown(self) -> None:   # pragma: no cover - needs GL context
        """Release the PBO handles. Safe on an uninitialised
        uploader."""
        if not self._initialised:
            return
        try:
            from OpenGL.GL import glDeleteBuffers
            glDeleteBuffers(len(self._pbos), self._pbos)
        except Exception as exc:   # noqa: BLE001
            logger.info("PBO shutdown swallowed: %s", exc)
        self._pbos = []
        self._initialised = False
