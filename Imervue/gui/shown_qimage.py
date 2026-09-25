"""A file as the viewer shows it, as a QImage — for Qt widgets that show a second copy.

``QImage(path)`` / ``QPixmap(path)`` ignore the EXIF orientation (a portrait
phone photo lies on its side) and the embedded colour profile (Display P3
looks washed out), and cannot open a camera RAW or HEIC at all. The side
panels, compare views, folder previews and the clipboard copy go through
:func:`shown_qimage` instead, the viewer's own decode.
"""
from __future__ import annotations

import logging

from PySide6.QtGui import QImage

from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.system.qimage_convert import pil_to_qimage

logger = logging.getLogger("Imervue.shown_qimage")


def shown_qimage(path: str, *, max_edge: int | None = None) -> QImage:
    """Return *path* decoded as the viewer shows it: upright, sRGB, RAW developed.

    *max_edge* scales the long side down to it (through the fast thumbnail
    decode when that is big enough). An unreadable file gives a null QImage,
    as ``QImage(path)`` did, so callers keep testing ``isNull()``.
    """
    from Imervue.gpu_image_view.images.image_loader import decode_image
    try:
        return pil_to_qimage(decode_image(path, max_edge=max_edge))
    except IMAGE_READ_ERRORS:
        logger.debug("Could not decode %s", path, exc_info=True)
        return QImage()
