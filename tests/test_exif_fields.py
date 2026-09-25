"""Tests for the EXIF editor's pure field logic."""
from __future__ import annotations

import sys

import pytest
from PIL import Image

from Imervue.image.exif_fields import (
    USER_COMMENT, apply_fields, can_edit, decode_user_comment, encode_user_comment,
    read_fields, save_fields,
)

_ARTIST, _MAKE = 0x013B, 0x010F


def _round_trip(exif: Image.Exif) -> Image.Exif:
    again = Image.Exif()
    again.load(exif.tobytes())
    return again


@pytest.mark.parametrize("endian", ["<", ">"])
@pytest.mark.parametrize("text", ["plain", "中文 comment", "é"])
def test_user_comment_round_trips_in_either_byte_order(endian, text):
    exif = Image.Exif()
    exif.endian = endian
    raw = encode_user_comment(text, exif)
    assert raw.startswith(b"ASCII\0\0\0" if text.isascii() else b"UNICODE\0")
    assert decode_user_comment(raw, exif) == text


@pytest.mark.parametrize(("raw", "shown"), [
    (b"UNICODE\x00" + "é".encode("utf-16-be"), "é"),    # piexif's big-endian UNICODE
    (b"no prefix here", "no prefix here"),
    (b"", ""),
    ("already text", "already text"),
])
def test_decode_user_comment(raw, shown):
    assert decode_user_comment(raw, Image.Exif()) == shown


def test_fields_round_trip_through_pillow_including_non_ascii():
    """Pillow writes a str ASCII tag through "?" and reads UTF-8 bytes back as Latin-1."""
    exif = Image.Exif()
    apply_fields(exif, {_ARTIST: "陳 Ada é", USER_COMMENT: "中文 comment", _MAKE: "Canon"})
    values = read_fields(_round_trip(exif))
    assert values[_ARTIST] == "陳 Ada é"
    assert values[USER_COMMENT] == "中文 comment"
    assert values[_MAKE] == "Canon"
    assert values[0x8298] == ""                                   # absent → empty


def test_an_empty_field_removes_the_tag_and_others_are_left_alone():
    exif = Image.Exif()
    apply_fields(exif, {_ARTIST: "Ada", _MAKE: "Canon"})
    apply_fields(exif, {_ARTIST: ""})
    again = _round_trip(exif)
    assert _ARTIST not in again
    assert read_fields(again)[_MAKE] == "Canon"


def test_latin1_text_that_is_not_utf8_is_shown_as_is():
    exif = Image.Exif()
    exif[_ARTIST] = b"Ren\xe9"                                 # a Latin-1 file from another tool
    assert read_fields(_round_trip(exif))[_ARTIST] == "René"


@pytest.mark.parametrize(("name", "expected"), [
    ("a.jpg", True), ("a.JPEG", True), ("a.webp", True),
    ("a.png", False), ("a.tif", False), ("a.cr2", False), ("a.heic", False),
])
def test_can_edit(name, expected):
    assert can_edit(name) is expected


def test_save_refuses_an_uneditable_file(tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGB", (4, 4)).save(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="can't rewrite the EXIF"):
        save_fields(path, {_ARTIST: "Ada"})
    assert path.read_bytes() == before


def test_save_into_webp_needs_no_piexif(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "piexif", None)
    path = tmp_path / "a.webp"
    Image.new("RGB", (8, 8)).save(path)
    save_fields(path, {_ARTIST: "Ada", USER_COMMENT: "中文"})
    with Image.open(path) as img:
        values = read_fields(img.getexif())
    assert (values[_ARTIST], values[USER_COMMENT]) == ("Ada", "中文")
