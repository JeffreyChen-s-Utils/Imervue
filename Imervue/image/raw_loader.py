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

import contextlib
import logging
from pathlib import Path

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
        with contextlib.suppress(Exception):
            raw.close()
        raise
    return raw


def _wrap_close_to_release(raw, region, fd):
    """Make ``raw.close()`` also close the mmap *region* and *fd*.

    RawPy.close() only tears down the libraw context, so the mmap + fd otherwise
    leak. Extracted so the release wiring is unit-testable without rawpy."""
    original_close = raw.close

    def _close_all() -> None:
        try:
            original_close()
        finally:
            with contextlib.suppress(Exception):
                region.close()
            with contextlib.suppress(Exception):
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
        with contextlib.suppress(Exception):
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
