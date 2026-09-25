"""The file extensions Imervue opens, defined once.

The viewer, the file tree, drag-and-drop, the Open dialogs and the library
scanner used to carry their own hand-typed lists, and each one missed a
different format (HEIC, JPEG XL, video). Every reader of "what can we open"
takes its set from here instead.
"""
from __future__ import annotations

from Imervue.image.avif_support import AVIF_EXTENSIONS
from Imervue.image.heif_support import HEIF_EXTENSIONS, ensure_heif_opener
from Imervue.image.jxl_support import JXL_EXTENSIONS, ensure_jxl_opener
from Imervue.image.video_frames import VIDEO_EXTENSIONS

RAW_EXTENSIONS: frozenset[str] = frozenset({
    ".cr2", ".cr3", ".crw",            # Canon
    ".nef", ".nrw",                    # Nikon
    ".arw", ".srf", ".sr2",            # Sony
    ".dng",                            # Adobe DNG (phones, Leica, Pentax, Ricoh...)
    ".raf",                            # Fujifilm
    ".orf",                            # Olympus / OM System
    ".rw2", ".rwl",                    # Panasonic, Leica
    ".pef",                            # Pentax
    ".srw",                            # Samsung
    ".3fr", ".iiq", ".mef", ".mos",    # Hasselblad, Phase One, Mamiya, Leaf
    ".erf", ".mrw", ".kdc", ".dcr",    # Epson, Minolta, Kodak
})
"""Camera RAW formats, decoded through rawpy (LibRaw).

Sigma's ``.x3f`` is left out: LibRaw reads it only when built with
``USE_X3FTOOLS``, which rawpy's wheels are not. So is the bare ``.raw``,
which too many non-camera files share.
"""

JPEG_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".jpe", ".jfif", ".jif"})
"""Every name a JPEG goes by.

Chrome and Edge on Windows often save a downloaded JPEG as ``.jfif``; Pillow
reads the file by its content, so each of these opens as a JPEG.
"""

STILL_IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif", ".apng", ".svg",
}) | JPEG_EXTENSIONS | RAW_EXTENSIONS | HEIF_EXTENSIONS | AVIF_EXTENSIONS | JXL_EXTENSIONS
"""Every still-image format the viewer opens; what the library indexes."""

VIEWER_EXTENSIONS: frozenset[str] = STILL_IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
"""Everything the viewer opens, videos included (shown by their poster frame)."""

RASTER_EXTENSIONS: frozenset[str] = STILL_IMAGE_EXTENSIONS - {".svg"}
"""The still formats a tool without Qt decodes (the CLI, the MCP server).

SVG is left out: it needs Qt to rasterise.
"""


def ensure_pillow_opener(ext: str) -> None:
    """Register the optional Pillow codec ``ext`` needs (HEIC / HEIF or JPEG XL), if any.

    A no-op for every other extension (AVIF included: Pillow reads it
    itself), and when the codec package is missing.
    """
    ext = ext.lower()
    if ext in HEIF_EXTENSIONS:
        ensure_heif_opener()
    elif ext in JXL_EXTENSIONS:
        ensure_jxl_opener()
