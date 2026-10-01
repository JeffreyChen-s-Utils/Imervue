"""Which of the source file's metadata an exported copy carries.

Export writes a new file from the decoded pixels, so nothing of the source's
EXIF reaches it unless it is handed to the save. The user picks a policy:
everything descriptive, everything but the location, or nothing. Pure logic
(the Pillow read aside); the export dialogs own the choice and its setting.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from Imervue.image.exif_merge import read_exif
from Imervue.image.exif_types import restore_types
from Imervue.image.formats import ensure_pillow_opener
from Imervue.image.in_place_save import descriptive_exif
from Imervue.image.raw_exif import RAW_EXIF_EXTENSIONS
from Imervue.image.read_errors import IMAGE_READ_ERRORS

METADATA_ALL = "all"
METADATA_NO_LOCATION = "no_location"
METADATA_NONE = "none"
METADATA_POLICIES: tuple[str, ...] = (METADATA_ALL, METADATA_NO_LOCATION, METADATA_NONE)
DEFAULT_METADATA_POLICY = METADATA_NO_LOCATION
"""Camera, lens and capture date survive; GPS does not leak into a shared copy by default."""

SETTING_KEY = "export_metadata"


def policy_or_default(value: object) -> str:
    """Return *value* when it names a policy, else the default (settings are external input)."""
    return value if value in METADATA_POLICIES else DEFAULT_METADATA_POLICY


def export_exif(source_path: str | Path, policy: str) -> Image.Exif | None:
    """Return the EXIF an export of *source_path* should carry under *policy*.

    ``None`` for :data:`METADATA_NONE`, a source Pillow can't read, or one
    without descriptive EXIF. :data:`METADATA_NO_LOCATION` drops the GPS IFD
    and the XMP packet, which can hold the position too. The orientation is
    never carried: exported pixels are already upright; nor is the camera
    maker note, which a NEF or ORF has too large for a JPEG.
    """
    carried = _carried(source_path, policy)
    return None if carried is None else carried[0]


def export_save_options(source_path: str | Path, policy: str) -> dict:
    """``save_image`` extras for *policy*: ``{"exif": <bytes>}``, or ``{}`` when nothing is carried.

    Bytes rather than an ``Image.Exif``: every writer takes them, the
    pillow-heif and JPEG XL plugins included. The entry types Pillow's
    serialiser gets wrong are put back from the source.
    """
    carried = _carried(source_path, policy)
    if carried is None:
        return {}
    exif, original = carried
    return {"exif": restore_types(exif.tobytes(), original)}


def _carried(source_path: str | Path, policy: str) -> tuple[Image.Exif, bytes | None] | None:
    """The EXIF to carry and the source's raw EXIF block; None when nothing is carried."""
    policy = policy_or_default(policy)
    if policy == METADATA_NONE:
        return None
    keep_location = policy != METADATA_NO_LOCATION
    ext = Path(source_path).suffix.lower()
    if ext in RAW_EXIF_EXTENSIONS:
        # A CR3 / RW2 / ORF / RAF: Pillow can't open it, its EXIF is read directly.
        exif, original = descriptive_exif(read_exif(source_path), keep_location=keep_location,
                                         keep_maker_note=False), None
    else:
        ensure_pillow_opener(ext)
        try:
            with Image.open(source_path) as source:
                exif = descriptive_exif(source, keep_location=keep_location, keep_maker_note=False)
                original = source.info.get("exif")
        except IMAGE_READ_ERRORS:
            return None
    if not len(exif):
        return None
    return exif, original if isinstance(original, bytes) else None
