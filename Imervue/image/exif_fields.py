"""The EXIF editor's fields: read, apply and save them without piexif.

Pure logic behind ``gui/exif_editor.py``. The model is Pillow's
``Image.Exif``. A JPEG or WebP is saved by swapping only its EXIF block
(``in_place_save.rewrite_exif``), so the image data and every other tag stay
as they were; other formats aren't editable.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from Imervue.image.formats import ensure_pillow_opener
from Imervue.image.in_place_save import can_rewrite_exif, rewrite_exif

_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
USER_COMMENT = 0x9286

# EXIF UserComment starts with an 8-byte character-code prefix.
_ASCII_PREFIX = b"ASCII\x00\x00\x00"
_UNICODE_PREFIX = b"UNICODE\x00"
_PREFIX_LENGTH = 8


@dataclass(frozen=True)
class ExifField:
    """One editable tag: where it lives and how the dialog labels it."""

    tag: int
    in_exif_ifd: bool
    label_key: str
    label: str


EDITABLE_FIELDS: tuple[ExifField, ...] = (
    ExifField(0x010E, False, "exif_edit_description", "Description"),
    ExifField(0x013B, False, "exif_edit_artist", "Artist"),
    ExifField(0x8298, False, "exif_edit_copyright", "Copyright"),
    ExifField(0x010F, False, "exif_edit_make", "Make"),
    ExifField(0x0110, False, "exif_edit_model", "Model"),
    ExifField(USER_COMMENT, True, "exif_edit_user_comment", "User Comment"),
)


def _utf16(exif: Image.Exif) -> str:
    """UTF-16 in the block's byte order, as the EXIF spec (and piexif) write UNICODE comments."""
    return "utf-16-le" if exif.endian == "<" else "utf-16-be"


def decode_user_comment(raw: bytes | str, exif: Image.Exif) -> str:
    """Text of an EXIF UserComment, without its 8-byte character-code prefix.

    A value without a recognised prefix is shown as UTF-8 (Pillow may also
    hand back an already-decoded ``str``).
    """
    if isinstance(raw, str):
        return raw
    prefix, body = raw[:_PREFIX_LENGTH], raw[_PREFIX_LENGTH:]
    if prefix == _UNICODE_PREFIX:
        return body.decode(_utf16(exif), errors="replace")
    if prefix == _ASCII_PREFIX:
        return body.decode("ascii", errors="replace")
    return raw.decode("utf-8", errors="replace")


def encode_user_comment(text: str, exif: Image.Exif) -> bytes:
    """UserComment bytes for *text*: ASCII when it fits, else UNICODE (never lossy ``?``)."""
    if text.isascii():
        return _ASCII_PREFIX + text.encode("ascii")
    return _UNICODE_PREFIX + text.encode(_utf16(exif))


def _text(value: bytes | str) -> str:
    """An ASCII-typed tag's text, read as the UTF-8 the editor (and piexif) wrote.

    Pillow decodes ASCII tags as Latin-1, which turns UTF-8 into mojibake;
    re-encoding recovers the bytes. Text that isn't UTF-8 stays as Pillow read it.
    """
    raw = value if isinstance(value, bytes) else value.encode("latin-1", errors="strict")
    try:
        return raw.decode("utf-8").rstrip("\x00")
    except UnicodeDecodeError:
        return raw.decode("latin-1").rstrip("\x00")


def _ifd_for(exif: Image.Exif, field: ExifField):
    return exif.get_ifd(_EXIF_IFD) if field.in_exif_ifd else exif


def read_fields(exif: Image.Exif) -> dict[int, str]:
    """The editable fields' current text, keyed by tag ("" when absent)."""
    values = {}
    for field in EDITABLE_FIELDS:
        raw = _ifd_for(exif, field).get(field.tag, "")
        if field.tag == USER_COMMENT:
            values[field.tag] = decode_user_comment(raw, exif)
        elif isinstance(raw, (bytes, str)):
            try:
                values[field.tag] = _text(raw)
            except UnicodeEncodeError:   # already real text beyond Latin-1
                values[field.tag] = raw
        else:
            values[field.tag] = str(raw)
    return values


def apply_fields(exif: Image.Exif, values: Mapping[int, str]) -> None:
    """Write *values* (tag → text) into *exif*; an empty text removes the tag."""
    for field in EDITABLE_FIELDS:
        if field.tag not in values:
            continue
        text = values[field.tag]
        ifd = _ifd_for(exif, field)
        if not text:
            ifd.pop(field.tag, None)
            continue
        # Bytes, not str: Pillow writes a str ASCII tag through "?" replacement.
        ifd[field.tag] = (encode_user_comment(text, exif) if field.tag == USER_COMMENT
                          else text.encode("utf-8"))
    if exif.get_ifd(_EXIF_IFD):
        exif[_EXIF_IFD] = exif.get(_EXIF_IFD, 0)   # the save writes the IFD and its real offset


def can_edit(path: str | Path) -> bool:
    """Whether :func:`save_fields` can write *path* (a JPEG or WebP)."""
    return can_rewrite_exif(path)


def load_exif(path: str | Path) -> Image.Exif:
    """The EXIF of *path* as Pillow reads it; empty for a file without one.

    Raises what Pillow raises for an unreadable file (``IMAGE_READ_ERRORS``).
    """
    ensure_pillow_opener(Path(path).suffix.lower())
    with Image.open(path) as img:
        exif = img.getexif()
        exif.get_ifd(_EXIF_IFD)    # load the sub-IFDs before the file closes
        exif.get_ifd(_GPS_IFD)
    return exif


def save_fields(path: str | Path, values: Mapping[int, str]) -> None:
    """Write *values* into the EXIF of *path*, replacing the file in one step.

    The image data, other tags and thumbnail stay byte for byte. Raises
    ``ValueError`` for a file :func:`can_edit` refuses or a malformed one,
    ``OSError`` when the write fails.
    """
    rewrite_exif(path, lambda exif: apply_fields(exif, values))
