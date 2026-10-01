"""Fit Pillow's decompression-bomb limit to this machine, and decode giant pictures one at a time.

Pillow refuses to open any image of more than twice ``Image.MAX_IMAGE_PIXELS``
(89.5 MP by default, so 179 MP) - a guard for a server decoding uploads. On
the desktop it kept a stitched panorama of 200 MP from opening at all; not
even its size could be read. :func:`raise_pixel_limit` moves the refusal to
where decoding would really need all of the memory, never below Pillow's own.

A picture past Pillow's default costs gigabytes to decode, and the thumbnail
workers decode several files at once: :func:`decode_slot` lets one such
picture decode at a time, so a folder of panoramas cannot add them up.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from PIL import Image

#: Pillow's own ``MAX_IMAGE_PIXELS`` (it refuses twice this).
DEFAULT_MAX_IMAGE_PIXELS = int(1024 * 1024 * 1024 // 4 // 3)

# What one decoded pixel can cost at once in the viewer: the RGBA array, a
# conversion copy and a share of the tile pyramid and its upload.
_BYTES_PER_PIXEL = 12

_GIANT_DECODES = threading.BoundedSemaphore(1)


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [   # the ctypes layout of MEMORYSTATUSEX
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def total_memory_bytes() -> int | None:
    """This machine's physical memory in bytes, or None when it can't be read."""
    if sys.platform == "win32":
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys)
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):   # an unknown name, or no sysconf at all
        return None


def pixel_limit_for(memory_bytes: int | None) -> int:
    """``Image.MAX_IMAGE_PIXELS`` for *memory_bytes* of RAM; Pillow's own when unknown or larger.

    Pillow refuses twice the limit, so the refusal lands where a decode would
    take all of the memory: 16 GB (about 17e9 bytes) refuses past 1.4 gigapixels.
    """
    if not memory_bytes or memory_bytes <= 0:
        return DEFAULT_MAX_IMAGE_PIXELS
    return max(DEFAULT_MAX_IMAGE_PIXELS, memory_bytes // (2 * _BYTES_PER_PIXEL))


def raise_pixel_limit() -> int:
    """Set Pillow's pixel limit for this machine and return it (``configure_pillow`` calls it)."""
    limit = pixel_limit_for(total_memory_bytes())
    Image.MAX_IMAGE_PIXELS = limit
    return limit


@contextmanager
def decode_slot(pixels: int) -> Iterator[None]:
    """Hold the one slot for decoding a picture past Pillow's default limit; free below it."""
    if pixels <= DEFAULT_MAX_IMAGE_PIXELS:
        yield
        return
    with _GIANT_DECODES:
        yield
