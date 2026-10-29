"""Locate an image's XMP sidecar and read its metadata, else the image's embedded packet."""
from __future__ import annotations

from pathlib import Path

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

from Imervue.image.xmp_sidecar_parse import _from_root
from Imervue.image.xmp_sidecar_schema import _RATING_MAX, XmpData

_EXIF_RATING = 0x4746          # 0-5 stars, written by Windows Explorer and some cameras
_EXIF_RATING_PERCENT = 0x4749  # the same as a 0-100 percentage


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _existing_sidecar(image_path: str | Path) -> Path | None:
    """The sidecar beside *image_path*: ``foo.xmp``, else ``foo.jpg.xmp``; None without one."""
    image = Path(image_path)
    for candidate in (image.with_suffix(".xmp"), image.with_name(image.name + ".xmp")):
        if candidate.is_file():
            return candidate
    return None


def sidecar_path_for(image_path: str | Path) -> Path:
    """Return the sidecar path for ``image_path``: the existing one, else ``<image>.xmp``.

    Adobe's convention replaces the extension (``foo.jpg`` \u2192 ``foo.xmp``)
    and wins when both files exist; darktable and digiKam append it
    (``foo.jpg.xmp``), and that file is read and merged into when it is the
    only one. A new sidecar is written the Adobe way.
    """
    return _existing_sidecar(image_path) or Path(image_path).with_suffix(".xmp")


def has_sidecar(image_path: str | Path) -> bool:
    """Return True if a sidecar exists for ``image_path``."""
    return _existing_sidecar(image_path) is not None


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def load(image_path: str | Path) -> XmpData:
    """Read the metadata for ``image_path`` and return an ``XmpData``.

    The sidecar when there is one; otherwise what the image file carries
    itself (:func:`load_embedded`) \u2014 Lightroom writes a JPEG's rating and
    keywords into the file rather than a sidecar, and so does Windows
    Explorer. Returns a default (empty) ``XmpData`` if there is nothing or
    the XML is malformed \u2014 we never raise on bad user files, because losing
    the image view because of a broken sidecar would be a poor UX.
    """
    path = _existing_sidecar(image_path)
    if path is None:
        return load_embedded(image_path)
    try:
        tree = DefusedET.parse(str(path))
        root = tree.getroot()
    except (DefusedET.ParseError, OSError, DefusedXmlException):
        # DefusedXmlException covers a sidecar carrying a DTD / entity /
        # external reference (defusedxml rejects these to block XXE and
        # billion-laughs). It subclasses ValueError, so it slipped past the
        # old (ParseError, OSError) tuple and crashed keyword indexing /
        # smart-album evaluation instead of degrading to an empty sidecar.
        return XmpData()
    return _from_root(root)


def load_embedded(image_path: str | Path) -> XmpData:
    """The metadata the image file carries itself: its XMP packet, then its EXIF rating.

    The XMP packet is the one Pillow finds in a JPEG's APP1, a PNG's iTXt, a
    WebP chunk or TIFF tag 700, or the one a CR3 / RW2 / ORF / RAF carries
    (:func:`~Imervue.image.raw_exif.raw_xmp`), where the camera puts its
    in-camera rating. A photo rated in Windows Explorer or in camera may only
    have the EXIF ``Rating`` (0x4746) or ``RatingPercent`` (0x4749); that
    fills in the rating when the packet has none. Empty for an unreadable
    file or one without either.
    """
    packet, exif_rating = _embedded_metadata(image_path)
    data = XmpData()
    if packet:
        try:
            data = _from_root(DefusedET.fromstring(packet))
        except (DefusedET.ParseError, DefusedXmlException):
            data = XmpData()
    if not data.rating and exif_rating:
        data.rating = exif_rating
    return data


def _embedded_metadata(image_path: str | Path) -> tuple[bytes | None, int]:
    """``(XMP packet, EXIF stars)`` stored inside *image_path*; ``(None, 0)`` when unreadable."""
    from PIL import Image

    from Imervue.image.metadata_sync import percent_to_rating
    from Imervue.image.raw_exif import RAW_EXIF_EXTENSIONS
    from Imervue.image.read_errors import IMAGE_READ_ERRORS
    if Path(image_path).suffix.lower() in RAW_EXIF_EXTENSIONS:
        # CR3 / RW2 / ORF / RAF: Pillow can't open them; a camera keeps its rating here.
        from Imervue.image.exif_merge import read_exif
        from Imervue.image.raw_exif import raw_xmp
        try:
            packet = raw_xmp(image_path)
        except OSError:
            return None, 0
        exif = read_exif(image_path)
    else:
        try:
            with Image.open(image_path) as img:
                packet = img.info.get("xmp")
                exif = img.getexif()
        except IMAGE_READ_ERRORS:
            return None, 0
    if isinstance(packet, str):
        packet = packet.encode("utf-8")
    rating = exif.get(_EXIF_RATING)
    if rating is None and exif.get(_EXIF_RATING_PERCENT) is not None:
        rating = percent_to_rating(exif[_EXIF_RATING_PERCENT])
    try:
        stars = max(0, min(_RATING_MAX, int(rating or 0)))
    except (TypeError, ValueError):
        stars = 0
    return (packet if isinstance(packet, bytes) and packet.strip() else None), stars
