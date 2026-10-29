"""Contracts of Imervue.image.raw_exif's byte parsing, pinned on hand-built byte blobs.

``tests/test_raw_exif.py`` covers the readers end to end; these pin the box
walk, the JPEG marker walk, the TIFF magic patch and the Panasonic tag drop at
their edges: extended and to-the-end box sizes, boxes that lie about their
size, markers that end the search, and which damage is swallowed.
"""
from __future__ import annotations

import io
import struct

import pytest
from PIL import ExifTags, Image

from Imervue.image import raw_exif as module
from Imervue.image.raw_exif import jpeg_app1, raf_jpeg_header, raw_exif, raw_xmp, top_level_box

_CANON_UUID = bytes.fromhex("85c0b687820f11e08111f4ce462b6a48")
_XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")
_EXIF_SIGNATURE = b"Exif\x00\x00"
_XMP_SIGNATURE = b"http://ns.adobe.com/xap/1.0/\x00"
_MODEL = "Canon EOS R5"
_EMPTY_IFD = b"II*\x00" + struct.pack("<IHI", 8, 0, 0)


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def _tiff(tags: dict, *, big_endian: bool = False) -> bytes:
    exif = Image.Exif()
    exif.endian = ">" if big_endian else "<"
    exif.update(tags)
    return exif.tobytes()[6:]


def _with_subs(ifd0: dict, sub: dict | None = None, gps: dict | None = None) -> bytes:
    exif = Image.Exif()
    exif.endian = "<"
    exif.update(ifd0)
    if sub is not None:
        exif.get_ifd(ExifTags.IFD.Exif).update(sub)
        exif[ExifTags.IFD.Exif] = 0
    if gps is not None:
        exif.get_ifd(ExifTags.IFD.GPSInfo).update(gps)
        exif[ExifTags.IFD.GPSInfo] = 0
    return exif.tobytes()[6:]


def _file(tmp_path, name: str, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _cr3_moov(canon_boxes: bytes) -> bytes:
    return _box(b"ftyp", b"crx ") + _box(b"moov", _box(b"uuid", _CANON_UUID + canon_boxes))


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes((0xFF, marker)) + struct.pack(">H", 2 + len(payload)) + payload


def _raf(jpeg: bytes, *, offset: int = 148, length: int | None = None) -> bytes:
    header = b"FUJIFILMCCD-RAW 0201FF383501".ljust(84, b"\0")
    header += struct.pack(">II", offset, len(jpeg) if length is None else length)
    return header.ljust(offset, b"\0") + jpeg


# ---------------------------------------------------------------------------
# top_level_box: the ISO-BMFF walk that reads only box headers
# ---------------------------------------------------------------------------


def _top(data: bytes, kind: bytes = b"moov", uuid: bytes | None = None):
    return top_level_box(io.BytesIO(data), kind, uuid)


def test_top_level_box_skips_earlier_boxes():
    assert _top(_box(b"ftyp", b"crx ") + _box(b"free", b"zz") + _box(b"moov", b"p")) == b"p"


def test_top_level_box_reads_an_extended_size():
    assert _top(struct.pack(">I4sQ", 1, b"moov", 20) + b"abcd" + b"tail") == b"abcd"


def test_top_level_box_size_zero_runs_to_the_end_of_the_file():
    assert _top(_box(b"free", b"") + struct.pack(">I4s", 0, b"moov") + b"xyz") == b"xyz"


@pytest.mark.parametrize("data", [
    b"",                                                   # nothing to walk
    b"moov",                                               # shorter than a header
    _box(b"ftyp", b"crx "),                                # no such box
    struct.pack(">I4s", 100, b"moov") + b"ab",             # claims more than is left
    struct.pack(">I4s", 4, b"moov") + b"abcd",             # claims less than its header
    struct.pack(">I4sQ", 1, b"moov", 8) + b"abcd",         # extended size under 16
    _box(b"ftyp", b"x") + struct.pack(">I4s", 3, b"free") + _box(b"moov", b"p"),
])
def test_top_level_box_none_cases(data):
    assert _top(data) is None


def test_top_level_box_picks_a_uuid_box_by_its_uuid_and_drops_it():
    data = _box(b"uuid", b"o" * 16 + b"other") + _box(b"uuid", _XMP_UUID + b"mine")
    assert _top(data, b"uuid", _XMP_UUID) == b"mine"
    assert _top(data, b"uuid") == b"o" * 16 + b"other"   # no uuid asked: the first, uuid kept


def test_top_level_box_uuid_box_too_short_for_its_uuid_is_none():
    # The 12-byte box's uuid "matches" by running into the next bytes of the file.
    data = struct.pack(">I4s", 12, b"uuid") + _XMP_UUID[:4] + _XMP_UUID[4:] + b"\0" * 8
    assert _top(data, b"uuid", _XMP_UUID) is None


def test_top_level_box_empty_payload_is_empty_bytes():
    assert _top(_box(b"moov", b"")) == b""


def test_top_level_box_reads_from_the_start_whatever_the_handle_position():
    handle = io.BytesIO(_box(b"moov", b"p"))
    handle.seek(5)
    assert top_level_box(handle, b"moov") == b"p"


# ---------------------------------------------------------------------------
# CR3: the Canon metadata uuid box inside moov
# ---------------------------------------------------------------------------


def test_cr3_ifd0_only_has_no_sub_ifds(tmp_path):
    exif = raw_exif(_file(tmp_path, "a.cr3", _cr3_moov(_box(b"CMT1", _tiff({272: _MODEL})))))
    assert dict(exif) == {272: _MODEL}


def test_cr3_sub_ifds_are_attached_with_pointer_zero(tmp_path):
    boxes = (_box(b"CMT1", _tiff({272: _MODEL}, big_endian=True))
             + _box(b"CMT2", _tiff({0x8827: 200}))
             + _box(b"CMT4", _tiff({0: b"\x02\x03\x00\x00", 1: "S"})))
    exif = raw_exif(_file(tmp_path, "a.cr3", _cr3_moov(boxes)))
    assert exif[ExifTags.IFD.Exif] == 0
    assert exif[ExifTags.IFD.GPSInfo] == 0
    assert exif.get_ifd(ExifTags.IFD.Exif)[0x8827] == 200
    assert exif.get_ifd(ExifTags.IFD.GPSInfo)[1] == "S"


def test_cr3_empty_sub_ifds_and_a_lone_gps_version_are_left_out(tmp_path):
    boxes = (_box(b"CMT1", _tiff({272: _MODEL})) + _box(b"CMT2", _EMPTY_IFD)
             + _box(b"CMT4", _tiff({0: b"\x02\x03\x00\x00"})))
    exif = raw_exif(_file(tmp_path, "a.cr3", _cr3_moov(boxes)))
    assert ExifTags.IFD.Exif not in exif
    assert ExifTags.IFD.GPSInfo not in exif


def test_cr3_inner_boxes_with_extended_and_to_the_end_sizes(tmp_path):
    cmt1 = _tiff({272: _MODEL})
    boxes = (struct.pack(">I4sQ", 1, b"CMT1", 16 + len(cmt1)) + cmt1
             + struct.pack(">I4s", 0, b"CMT2") + _tiff({0x8827: 800}))
    exif = raw_exif(_file(tmp_path, "a.cr3", _cr3_moov(boxes)))
    assert exif[272] == _MODEL
    assert exif.get_ifd(ExifTags.IFD.Exif)[0x8827] == 800


def test_cr3_an_inner_box_shorter_than_its_header_ends_the_walk(tmp_path):
    boxes = (_box(b"CMT1", _tiff({272: _MODEL})) + struct.pack(">I4s", 4, b"free")
             + _box(b"CMT2", _tiff({0x8827: 800})))
    exif = raw_exif(_file(tmp_path, "a.cr3", _cr3_moov(boxes)))
    assert exif[272] == _MODEL
    assert ExifTags.IFD.Exif not in exif


def test_cr3_only_the_first_canon_box_counts(tmp_path):
    first = _box(b"uuid", _CANON_UUID + _box(b"CMT2", _tiff({0x8827: 1})))
    second = _box(b"uuid", _CANON_UUID + _box(b"CMT1", _tiff({272: _MODEL})))
    assert raw_exif(_file(tmp_path, "a.cr3", _box(b"moov", first + second))) is None


@pytest.mark.parametrize("moov", [
    _box(b"uuid", _CANON_UUID + _box(b"CMT2", _tiff({0x8827: 1}))),   # no CMT1
    _box(b"uuid", _CANON_UUID + _box(b"CMT1", _EMPTY_IFD)),           # IFD0 without a tag
    struct.pack(">I4s", 1, b"uuid"),                                   # extended size cut off
])
def test_cr3_without_a_readable_ifd0_is_none(tmp_path, moov):
    assert raw_exif(_file(tmp_path, "a.cr3", _box(b"moov", moov))) is None


# ---------------------------------------------------------------------------
# RW2 / RWL / ORF: TIFF with the maker's magic number
# ---------------------------------------------------------------------------


def _panasonic(tmp_path, name: str, ifd0: dict, sub: dict | None = None):
    tiff = _with_subs(ifd0, sub)
    return _file(tmp_path, name, tiff[:2] + b"U\x00" + tiff[4:])


@pytest.mark.parametrize("name", ["P.RW2", "P.rwl"])
def test_panasonic_iso_fills_a_missing_exif_iso(tmp_path, name):
    exif = raw_exif(_panasonic(tmp_path, name, {0x0017: 125, 0x00FD: 1, 0x00FE: 0, 272: "X"},
                               {0x9003: "2021:05:10 20:11:06"}))
    assert sorted(exif) == [0x00FE, 272, ExifTags.IFD.Exif]
    assert exif.get_ifd(ExifTags.IFD.Exif)[0x8827] == 125


def test_panasonic_iso_never_overrides_the_exif_iso(tmp_path):
    exif = raw_exif(_panasonic(tmp_path, "P.RW2", {0x0017: 125, 272: "X"}, {0x8827: 400}))
    assert exif.get_ifd(ExifTags.IFD.Exif)[0x8827] == 400


def test_panasonic_without_an_exif_ifd_drops_the_iso(tmp_path):
    exif = raw_exif(_panasonic(tmp_path, "P.RW2", {0x0017: 125, 272: "X"}))
    assert dict(exif) == {272: "X"}


def test_panasonic_iso_that_is_not_a_number_is_not_copied(tmp_path):
    exif = raw_exif(_panasonic(tmp_path, "P.RW2", {0x0017: "125", 272: "X"}, {0x9003: "t"}))
    assert 0x8827 not in exif.get_ifd(ExifTags.IFD.Exif)


def test_panasonic_with_only_private_tags_is_empty_not_none(tmp_path):
    exif = raw_exif(_panasonic(tmp_path, "P.RW2", {0x0017: 125}))
    assert exif is not None
    assert len(exif) == 0


def test_orf_keeps_tags_below_the_baseline(tmp_path):
    tiff = _with_subs({0x0017: 125, 272: "E-M1"})
    exif = raw_exif(_file(tmp_path, "P.ORF", b"IIRO" + tiff[4:]))
    assert dict(exif) == {0x0017: 125, 272: "E-M1"}


def test_tiff_raw_sub_ifds_are_read_before_the_file_closes(tmp_path):
    tiff = _with_subs({272: "E-M1"}, {0x8827: 64}, {0: b"\x02\x03\x00\x00", 1: "N"})
    exif = raw_exif(_file(tmp_path, "P.orf", b"IIRO" + tiff[4:]))
    assert exif.get_ifd(ExifTags.IFD.Exif)[0x8827] == 64
    assert exif.get_ifd(ExifTags.IFD.GPSInfo)[1] == "N"


@pytest.mark.parametrize("data", [
    b"",
    b"XX*\x00\x08\x00\x00\x00",           # neither byte order
    b"IIRO" + _EMPTY_IFD[4:],             # IFD0 without a tag
])
def test_tiff_raw_without_tags_is_none(tmp_path, data):
    assert raw_exif(_file(tmp_path, "P.ORF", data)) is None


# ---------------------------------------------------------------------------
# RAF and the JPEG marker walk
# ---------------------------------------------------------------------------


def test_jpeg_app1_picks_the_segment_with_the_signature():
    jpeg = (b"\xff\xd8" + _segment(0xE0, b"JFIF\0") + _segment(0xE1, _XMP_SIGNATURE + b"x")
            + _segment(0xE1, _EXIF_SIGNATURE + b"e"))
    assert jpeg_app1(jpeg, _EXIF_SIGNATURE) == _EXIF_SIGNATURE + b"e"
    assert jpeg_app1(jpeg, _XMP_SIGNATURE) == _XMP_SIGNATURE + b"x"


@pytest.mark.parametrize("jpeg", [
    b"",
    b"\x89PNG" + _segment(0xE1, _EXIF_SIGNATURE),                       # not a JPEG
    b"\xff\xd8\xff",                                                    # marker cut short
    b"\xff\xd8" + _segment(0xDA, b"scan") + _segment(0xE1, _EXIF_SIGNATURE),
    b"\xff\xd8\x00\x00" + _segment(0xE1, _EXIF_SIGNATURE),              # not a marker
    b"\xff\xd8" + _segment(0xE2, _EXIF_SIGNATURE),                      # APP2, not APP1
])
def test_jpeg_app1_none_cases(jpeg):
    assert jpeg_app1(jpeg, _EXIF_SIGNATURE) is None


def test_jpeg_app1_payload_cut_short_is_what_is_there():
    jpeg = b"\xff\xd8\xff\xe1" + struct.pack(">H", 500) + _EXIF_SIGNATURE + b"ab"
    assert jpeg_app1(jpeg, _EXIF_SIGNATURE) == _EXIF_SIGNATURE + b"ab"


def test_raf_jpeg_header_follows_the_pointer_and_caps_the_length():
    data = _raf(b"\xff\xd8" + b"j" * 10)
    assert raf_jpeg_header(io.BytesIO(data)) == b"\xff\xd8" + b"j" * 10
    assert raf_jpeg_header(io.BytesIO(_raf(b"abcdef", length=3))) == b"abc"
    big = _raf(b"j" * (600 * 1024), length=600 * 1024)
    assert len(raf_jpeg_header(io.BytesIO(big))) == 512 * 1024


def test_raf_jpeg_header_needs_the_magic():
    assert raf_jpeg_header(io.BytesIO(b"FUJIFILMCCD-RAX " + b"\0" * 100)) is None


def test_raf_jpeg_header_cut_short_raises_struct_error():
    with pytest.raises(struct.error):
        raf_jpeg_header(io.BytesIO(b"FUJIFILMCCD-RAW " + b"\0" * 20))


def test_raf_jpeg_pointer_past_the_end_reads_nothing():
    assert raf_jpeg_header(io.BytesIO(_raf(b"", offset=148, length=50))) == b""


def test_raf_exif_comes_from_the_exif_app1(tmp_path):
    app1 = _EXIF_SIGNATURE + b"II*\x00" + _tiff({272: "X-T5"})[4:]
    raf = _raf(b"\xff\xd8" + _segment(0xE1, _XMP_SIGNATURE + b"x") + _segment(0xE1, app1))
    assert dict(raw_exif(_file(tmp_path, "a.raf", raf))) == {272: "X-T5"}


@pytest.mark.parametrize("jpeg", [
    b"\xff\xd8" + _segment(0xE0, b"JFIF\0"),                    # no Exif APP1
    b"\xff\xd8" + _segment(0xE1, _EXIF_SIGNATURE + _EMPTY_IFD),  # an empty IFD0
])
def test_raf_without_exif_tags_is_none(tmp_path, jpeg):
    assert raw_exif(_file(tmp_path, "a.raf", _raf(jpeg))) is None


@pytest.mark.parametrize(("payload", "expected"), [(b"<x/>", b"<x/>"), (b"", None)])
def test_raf_xmp_drops_the_signature(tmp_path, payload, expected):
    raf = _raf(b"\xff\xd8" + _segment(0xE1, _XMP_SIGNATURE + payload))
    assert raw_xmp(_file(tmp_path, "a.RAF", raf)) == expected


def test_raf_xmp_needs_the_magic(tmp_path):
    assert raw_xmp(_file(tmp_path, "a.raf", b"\0" * 200)) is None


# ---------------------------------------------------------------------------
# raw_exif / raw_xmp: dispatch and which errors pass through
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["gone.jpg", "gone.nef", "gone", "gone.cr2"])
def test_other_extensions_are_none_without_opening_the_file(tmp_path, name):
    assert raw_exif(tmp_path / name) is None
    assert raw_xmp(tmp_path / name) is None


@pytest.mark.parametrize("name", ["gone.CR3", "gone.Raf", "gone.orf", "gone.RW2", "gone.rwl"])
def test_a_missing_raw_raises_os_error(tmp_path, name):
    with pytest.raises(OSError):
        raw_exif(tmp_path / name)
    with pytest.raises(OSError):
        raw_xmp(tmp_path / name)


def test_paths_may_be_strings(tmp_path):
    path = _file(tmp_path, "a.cr3", _cr3_moov(_box(b"CMT1", _tiff({272: _MODEL}))))
    assert raw_exif(str(path))[272] == _MODEL


def _orf_xmp_entry(typ: int, count: int, data: bytes) -> bytes:
    """An ORF whose IFD0 is the one tag 700 of TIFF type *typ*."""
    value = data.ljust(4, b"\0") if len(data) <= 4 else struct.pack("<I", 26)
    tail = b"" if len(data) <= 4 else data
    return (b"IIRO" + struct.pack("<IH", 8, 1) + struct.pack("<HHI", 700, typ, count)
            + value + b"\0" * 4 + tail)


@pytest.mark.parametrize(("typ", "count", "data", "expected"), [
    (7, 6, b"<x/>ab", b"<x/>ab"),                    # UNDEFINED: the bytes
    (2, 6, b"<x/>a\0", b"<x/>a"),                    # ASCII: a str, encoded back
    (2, 1, b"\0", None),                             # an empty str
    (4, 1, struct.pack("<I", 7), None),              # a number is no packet
])
def test_tiff_raw_xmp_tag_types(tmp_path, typ, count, data, expected):
    assert raw_xmp(_file(tmp_path, "P.ORF", _orf_xmp_entry(typ, count, data))) == expected


def test_tiff_raw_xmp_of_damaged_metadata_is_none(tmp_path):
    assert raw_xmp(_file(tmp_path, "P.rw2", b"IIU\x00")) is None


def test_cr3_xmp_box_comes_after_moov(tmp_path):
    data = _cr3_moov(_box(b"CMT1", _tiff({272: _MODEL}))) + _box(b"uuid", _XMP_UUID + b"<x/>")
    assert raw_xmp(_file(tmp_path, "a.cr3", data)) == b"<x/>"


def test_cr3_empty_xmp_box_is_none(tmp_path):
    assert raw_xmp(_file(tmp_path, "a.cr3", _box(b"uuid", _XMP_UUID))) is None


def test_the_public_names_stay_on_the_module():
    for name in ("RAW_EXIF_EXTENSIONS", "raw_exif", "raw_xmp", "top_level_box",
                 "raf_jpeg_header", "jpeg_app1"):
        assert callable(getattr(module, name)) or name == "RAW_EXIF_EXTENSIONS"
