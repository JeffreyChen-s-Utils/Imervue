"""Memory-efficient RAW image loading.

``rawpy.imread(path)`` is the convenience entry point but it
reads the entire file into a Python ``bytes`` object before
handing it to libraw. For a 50 MB CR3 / NEF that's a redundant
copy on top of the decoded RGB buffer libraw produces — roughly
doubles the peak memory during a deep-zoom load.

This module routes around the convenience path:

* :func:`open_raw_efficient` uses ``RawPy.open_file`` — libraw's
  native file API, which streams from disk via the OS page cache
  instead of reading the whole file into Python memory first.
* :func:`open_raw_via_mmap` is a fallback for callers that need
  the buffer API (e.g. when reading from a custom file-like
  object), wrapping the file as ``mmap.mmap`` so libraw still
  operates on OS-managed memory rather than a Python ``bytes``
  copy.

Both helpers return an *unpacked* :class:`rawpy.RawPy` ready for
``postprocess`` / ``extract_thumb`` — same shape as the convenience
function but cheaper on memory.

The module imports ``rawpy`` lazily inside each helper so the
import cost is only paid when a RAW file is actually loaded;
JPEG-only sessions don't pull rawpy at all.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from Imervue.system.best_effort import best_effort

logger = logging.getLogger("Imervue.image.raw_loader")


def open_raw_efficient(path: str | Path):
    """Open ``path`` via libraw's native file API + unpack.

    Returns a :class:`rawpy.RawPy` instance ready for postprocess.
    The caller is responsible for the ``with`` / ``close`` lifecycle
    (the returned object supports context-manager protocol).
    """
    import rawpy
    raw = rawpy.RawPy()
    try:
        raw.open_file(str(path))
        raw.unpack()
    except Exception:
        # Close to release the libraw context if we successfully
        # opened the file but ``unpack`` failed — otherwise the
        # caller's ``with`` block never runs.
        with best_effort("close the RAW file after a failed unpack", logger):
            raw.close()
        raise
    return raw


# libraw ``flip`` values that turn the developed image a quarter turn.
_QUARTER_TURN_FLIPS = frozenset({5, 6})
# libraw ``flip`` -> ``numpy.rot90`` turns (counter-clockwise) that make an
# image in sensor orientation upright: 3 upside down, 5 / 6 a quarter turn.
_FLIP_TURNS = {3: 2, 5: 1, 6: -1}


def raw_dimensions(path: str | Path) -> tuple[int, int] | None:
    """Return the developed image's ``(width, height)``, or ``None`` if libraw can't read it.

    Reads libraw's header parse only (``open_file`` without ``unpack``), a few
    milliseconds even for a large file. Pillow is no substitute: it opens CR2 /
    NEF / DNG as TIFF and reports the size of the embedded preview. A
    quarter-turn orientation swaps the sides, as the developed image does.
    """
    import rawpy
    raw = rawpy.RawPy()
    try:
        raw.open_file(str(path))
        sizes = raw.sizes
    except rawpy.LibRawError:
        return None
    finally:
        raw.close()
    if sizes.flip in _QUARTER_TURN_FLIPS:
        return sizes.height, sizes.width
    return sizes.width, sizes.height


def _wrap_close_to_release(raw, region, fd):
    """Make ``raw.close()`` also close the mmap *region* and *fd*.

    RawPy.close() only tears down the libraw context, so the mmap + fd otherwise
    leak. Extracted so the release wiring is unit-testable without rawpy."""
    original_close = raw.close

    def _close_all() -> None:
        try:
            original_close()
        finally:
            with best_effort("unmap the RAW file", logger):
                region.close()
            with best_effort("close the RAW file handle", logger):
                fd.close()

    raw.close = _close_all
    return raw


def open_raw_via_mmap(path: str | Path):
    """Fallback path: mmap the file, hand the buffer to libraw via
    :meth:`rawpy.RawPy.open_buffer`. Used when ``open_file`` isn't
    available (very old libraw) or when the caller has another
    reason to prefer the buffer API.

    The returned RawPy instance holds a reference to the mmap'd
    region — caller MUST keep it alive via ``with``; closing the
    RawPy releases the mmap on top of the libraw context.
    """
    import mmap
    import rawpy
    fd = open(str(path), "rb")   # noqa: SIM115 - caller closes via context
    try:
        region = mmap.mmap(
            fd.fileno(), 0, access=mmap.ACCESS_READ,
        )
    except OSError:
        fd.close()
        raise
    raw = rawpy.RawPy()
    try:
        raw.open_buffer(region)
        raw.unpack()
    except Exception:
        with best_effort("close the RAW buffer after a failed unpack", logger):
            raw.close()
        region.close()
        fd.close()
        raise
    # RawPy.close() (run by the caller's ``with`` / close) doesn't know about our
    # mmap + fd, so on the success path they leaked — on Windows the file stayed
    # mapped and could not be deleted / renamed. Wrap close() to release all three.
    return _wrap_close_to_release(raw, region, fd)


def file_size_supports_mmap(file_size: int, minimum_bytes: int = 1_048_576) -> bool:
    """Pure helper: ``True`` when a file is large enough that
    mmap setup pays off. Sub-1 MB files are faster read straight
    into a buffer.

    Used by callers that compose mmap with another loader (PIL,
    imageio) and want a single source of truth for the cutoff."""
    if file_size <= 0:
        return False
    return int(file_size) >= int(minimum_bytes)


def develop_raw(path: str | Path, *, thumbnail: bool = False):
    """Develop the camera RAW at *path* to an HxWx3 uint8 array; ``OSError`` when libraw can't.

    Camera white balance, 8 bits. With *thumbnail* the embedded preview
    (JPEG or bitmap) is used when there is one, else a half-size develop.
    libraw's own ``LibRawError`` is not an ``OSError``, so every caller that
    handles an unreadable file through ``IMAGE_READ_ERRORS`` would miss a
    corrupt or unsupported RAW; it is re-raised as one. Qt-free, so the MCP
    server and the CLI can use it as well as the viewer.
    """
    import rawpy
    try:
        with open_raw_efficient(path) as raw:
            if thumbnail:
                return _embedded_preview(raw)
            return raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
            )
    except rawpy.LibRawError as err:
        raise OSError(f"libraw can't decode {path}: {err}") from err


def _embedded_preview(raw):
    # Imported here: rawpy and imageio cost ~190 ms at startup, and only a
    # RAW file needs them.
    import imageio
    import rawpy
    try:
        thumb = raw.extract_thumb()
        if thumb.format == rawpy.ThumbFormat.JPEG:
            preview = imageio.v3.imread(thumb.data)
        elif thumb.format == rawpy.ThumbFormat.BITMAP:
            preview = thumb.data
        else:
            raise ValueError("No valid embedded preview")
    # No or an unsupported embedded preview (a LibRawError, which is none of
    # the others), or one that does not decode (imageio).
    except (rawpy.LibRawError, ValueError, OSError, RuntimeError):
        return raw.postprocess(
            half_size=True,
            use_camera_wb=True,
            output_bps=8,
        )
    return upright_preview(preview, raw.sizes.flip)


def upright_preview(preview: np.ndarray, flip: int) -> np.ndarray:
    """Turn a RAW's embedded *preview* upright by libraw's *flip*.

    Cameras store the preview in sensor orientation, as the RAW itself, and
    libraw's ``postprocess`` turns only the developed image: a portrait shot's
    preview lay on its side. A preview already portrait for a quarter-turn
    *flip* was turned by the camera and is returned as is.
    """
    turns = _FLIP_TURNS.get(flip, 0)
    if not turns or (flip in _QUARTER_TURN_FLIPS and preview.shape[0] > preview.shape[1]):
        return preview
    return np.ascontiguousarray(np.rot90(preview, turns))
