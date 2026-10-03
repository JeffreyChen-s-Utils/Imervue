"""EXIF of the RAW containers Pillow can't open (Imervue.image.raw_exif), and its readers."""
from __future__ import annotations

import datetime as dt
import io
import struct

import pytest
from PIL import ExifTags, Image

from Imervue.image.raw_exif import RAW_EXIF_EXTENSIONS, raw_exif, raw_xmp

_CANON_UUID = bytes.fromhex("85c0b687820f11e08111f4ce462b6a48")
_TAKEN = "2021:05:10 20:11:06"


def _tiff(tags: dict, *, big_endian: bool = False) -> bytes:
    exif = Image.Exif()
    exif.endian = ">" if big_endian else "<"
    exif.update(tags)
    return exif.tobytes()[6:]      # drop the "Exif\0\0" prefix: a bare TIFF


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def _cr3(path, *, gps: dict | None = None, exif_ifd: dict | None = None):
    boxes = _box(b"CMT1", _tiff({271: "Canon", 272: "Canon EOS M50", 274: 1}))
    boxes += _box(b"CMT2", _tiff(exif_ifd or {0x9003: _TAKEN, 0x8827: 100,
                                               0xA434: "EF-M18-150mm"}))
    boxes += _box(b"CMT4", _tiff(gps or {0: b"\x02\x03\x00\x00"}))
    moov = _box(b"moov", _box(b"uuid", _CANON_UUID + boxes) + _box(b"mvhd", b"\x00" * 100))
    path.write_bytes(_box(b"ftyp", b"crx \x00\x00\x00\x01crx isom") + moov + _box(b"mdat", b"\x00" * 64))
    return path


def _with_exif_ifd(ifd0: dict, sub: dict, *, big_endian: bool = False) -> bytes:
    exif = Image.Exif()
    exif.endian = ">" if big_endian else "<"
    exif.update(ifd0)
    exif.get_ifd(ExifTags.IFD.Exif).update(sub)
    exif[ExifTags.IFD.Exif] = 0
    return exif.tobytes()[6:]


def _rw2(path):
    tiff = _with_exif_ifd({0x0017: 125, 0x002E: b"\xff\xd8" + b"j" * 5000, 271: "Panasonic",
                           272: "DMC-GX7"}, {0x9003: _TAKEN})
    path.write_bytes(tiff[:2] + b"U\x00" + tiff[4:])
    return path


def _orf(path, *, big_endian: bool = False):
    tiff = _with_exif_ifd({271: "OLYMPUS", 272: "E-M10"}, {0x9003: _TAKEN}, big_endian=big_endian)
    path.write_bytes((b"MMOR" if big_endian else b"IIRO") + tiff[4:])
    return path


def _raf(path):
    exif = Image.Exif()
    exif.update({271: "FUJIFILM", 272: "X-T20"})
    exif.get_ifd(ExifTags.IFD.Exif).update({0x9003: _TAKEN})
    exif[ExifTags.IFD.Exif] = 0
    jpeg = io.BytesIO()
    Image.new("RGB", (16, 8)).save(jpeg, "JPEG", exif=exif)
    offset = 148
    header = b"FUJIFILMCCD-RAW 0201FF383501" + b"\x00" * (84 - 28)
    header += struct.pack(">II", offset, len(jpeg.getvalue()))
    path.write_bytes(header.ljust(offset, b"\x00") + jpeg.getvalue())
    return path


def _taken(exif):
    return exif.get_ifd(ExifTags.IFD.Exif).get(0x9003)


# ---------------------------------------------------------------------------
# raw_exif
# ---------------------------------------------------------------------------


def test_the_extensions():
    assert frozenset({".cr3", ".rw2", ".rwl", ".orf", ".raf"}) == RAW_EXIF_EXTENSIONS


def test_cr3_reads_the_canon_metadata_boxes(tmp_path):
    exif = raw_exif(_cr3(tmp_path / "IMG_1.CR3"))
    assert (exif[271], exif[272]) == ("Canon", "Canon EOS M50")
    sub = exif.get_ifd(ExifTags.IFD.Exif)
    assert (sub[0x9003], sub[0x8827], sub[0xA434]) == (_TAKEN, 100, "EF-M18-150mm")
    assert ExifTags.IFD.GPSInfo not in exif     # only the version tag: no position


def test_cr3_with_a_position_carries_the_gps_ifd(tmp_path):
    gps = {0: b"\x02\x03\x00\x00", 1: "N", 2: (25.0, 2.0, 0.0), 3: "E", 4: (121.0, 30.0, 0.0)}
    exif = raw_exif(_cr3(tmp_path / "IMG_1.cr3", gps=gps))
    assert exif.get_ifd(ExifTags.IFD.GPSInfo)[1] == "N"


def test_rw2_drops_panasonics_private_tags_but_keeps_the_iso(tmp_path):
    """IFD0 carries the whole embedded JPEG under a private tag; the ISO lives there too."""
    exif = raw_exif(_rw2(tmp_path / "P1.RW2"))
    assert (exif[271], exif[272], _taken(exif)) == ("Panasonic", "DMC-GX7", _TAKEN)
    assert min(exif) >= 0x00FE
    assert exif.get_ifd(ExifTags.IFD.Exif)[0x8827] == 125


@pytest.mark.parametrize("big_endian", [False, True])
def test_orf_is_tiff_with_its_own_magic(tmp_path, big_endian):
    exif = raw_exif(_orf(tmp_path / "P1.ORF", big_endian=big_endian))
    assert (exif[272], _taken(exif)) == ("E-M10", _TAKEN)


def test_raf_reads_the_embedded_jpegs_exif(tmp_path):
    exif = raw_exif(_raf(tmp_path / "DSCF1.RAF"))
    assert (exif[271], exif[272], _taken(exif)) == ("FUJIFILM", "X-T20", _TAKEN)


def test_other_formats_are_not_read(tmp_path):
    path = tmp_path / "a.nef"
    path.write_bytes(b"II*\x00")
    assert raw_exif(path) is None


@pytest.mark.parametrize(("name", "content"), [
    ("a.cr3", b""),                                             # empty
    ("b.cr3", _box(b"ftyp", b"crx ")),                          # no moov
    ("c.cr3", _box(b"moov", _box(b"uuid", b"\x00" * 16))),      # no Canon box
    ("d.cr3", _box(b"moov", _box(b"uuid", _CANON_UUID + _box(b"CMT1", b"II*\x00junk")))),
    ("e.rw2", b"not a tiff at all"),
    ("f.orf", b"IIRO\xff\xff\xff\xff"),                        # IFD0 past the end
    ("g.raf", b"FUJIFILMCCD-RAW " + b"\x00" * 100),             # JPEG pointer to nothing
    ("h.raf", b"something else entirely"),
    ("i.cr3", struct.pack(">I4s", 4, b"moov")),                  # a box shorter than its header
])
def test_damaged_metadata_is_none(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)
    assert raw_exif(path) is None


def test_a_rw2_whose_embedded_jpeg_runs_past_the_first_megabytes(tmp_path):
    """Read from a fixed-size head, one value cut short cost Pillow the whole IFD0."""
    tiff = _with_exif_ifd({0x002E: b"\xff\xd8" + b"j" * (5 * 1024 * 1024), 271: "Panasonic",
                           272: "DC-G9"}, {0x9003: _TAKEN})
    path = tmp_path / "P1.RW2"
    path.write_bytes(tiff[:2] + b"U\x00" + tiff[4:])
    exif = raw_exif(path)
    assert (exif[272], _taken(exif)) == ("DC-G9", _TAKEN)


def test_a_cr3_box_walk_skips_large_boxes_without_reading_them(tmp_path):
    path = _cr3(tmp_path / "IMG_1.CR3")
    data = path.read_bytes()
    path.write_bytes(data[:24] + _box(b"free", b"\x00" * (6 * 1024 * 1024)) + data[24:])
    assert raw_exif(path)[272] == "Canon EOS M50"


def test_a_metadata_box_too_large_to_be_metadata_is_not_read(tmp_path):
    from Imervue.image import raw_exif as module
    path = tmp_path / "IMG_1.CR3"
    path.write_bytes(_box(b"moov", b"\x00" * 64))
    with open(path, "rb") as handle:
        assert module.top_level_box(handle, b"moov") == b"\x00" * 64
    with open(path, "rb") as handle, pytest.MonkeyPatch.context() as mp:
        mp.setattr(module, "_MAX_METADATA_BYTES", 63)
        assert module.top_level_box(handle, b"moov") is None


def test_a_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        raw_exif(tmp_path / "gone.cr3")


# ---------------------------------------------------------------------------
# the readers: sidebar, calendar, GPS, rename tokens, exports
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("make", [_cr3, _rw2, _orf, _raf])
def test_get_exif_data_reads_the_containers(tmp_path, make):
    """The EXIF sidebar, OSD, smart albums and the MCP server showed nothing for them."""
    from Imervue.image.exif_merge import get_exif_data
    suffix = {"_cr3": ".CR3", "_rw2": ".RW2", "_orf": ".ORF", "_raf": ".RAF"}[make.__name__]
    data = get_exif_data(make(tmp_path / f"shot{suffix}"))
    assert data["DateTimeOriginal"] == _TAKEN
    assert data["Model"]


def test_capture_date_of_a_cr3_is_when_it_was_taken(tmp_path):
    """It used to be the file's mtime: organised by date, a CR3 landed on the download day."""
    from Imervue.library.calendar_index import capture_datetime
    assert capture_datetime(_cr3(tmp_path / "IMG_1.CR3")) == dt.datetime(2021, 5, 10, 20, 11, 6)


def test_capture_date_of_a_tiff_based_raw_comes_from_the_exif_ifd(tmp_path):
    """Its sub-IFD was read after the file closed ("seek of closed file"): IFD0's time won."""
    from Imervue.library.calendar_index import capture_datetime
    exif = Image.Exif()
    exif[306] = "2020:01:01 00:00:00"                     # IFD0 DateTime: last edited
    exif.get_ifd(ExifTags.IFD.Exif)[0x9003] = "2019:06:07 08:09:10"
    exif[ExifTags.IFD.Exif] = 0
    path = tmp_path / "shot.tif"
    Image.new("RGB", (8, 8)).save(path, exif=exif)
    assert capture_datetime(path) == dt.datetime(2019, 6, 7, 8, 9, 10)


def test_gps_of_a_cr3(tmp_path):
    from Imervue.image.gps import extract_gps
    gps = {1: "S", 2: (25.0, 30.0, 0.0), 3: "W", 4: (121.0, 0.0, 0.0)}
    lat, lon = extract_gps(_cr3(tmp_path / "IMG_1.CR3", gps=gps))
    assert (lat, lon) == (pytest.approx(-25.5), pytest.approx(-121.0))


def test_rename_tokens_name_the_camera_of_a_raf(tmp_path, monkeypatch):
    from Imervue.library import token_rename
    monkeypatch.setattr(token_rename, "image_dimensions", lambda _p: (6000, 4000))
    meta = token_rename._gather_metadata(str(_raf(tmp_path / "DSCF1.RAF")), 1)  # noqa: SLF001
    assert meta["camera"] == "FUJIFILM X-T20"


def test_an_export_of_a_cr3_keeps_camera_lens_and_date(tmp_path):
    """Pillow can't open a CR3, so its exported copy carried no EXIF at all."""
    from Imervue.image.export_metadata import METADATA_NO_LOCATION, export_save_options
    gps = {1: "N", 2: (25.0, 2.0, 0.0), 3: "E", 4: (121.0, 30.0, 0.0)}
    options = export_save_options(_cr3(tmp_path / "IMG_1.CR3", gps=gps), METADATA_NO_LOCATION)
    out = tmp_path / "IMG_1.jpg"
    Image.new("RGB", (8, 8)).save(out, exif=options["exif"])
    with Image.open(out) as saved:
        exif = saved.getexif()
        sub = exif.get_ifd(ExifTags.IFD.Exif)
        assert (exif[272], sub[0x9003], sub[0xA434]) == ("Canon EOS M50", _TAKEN, "EF-M18-150mm")
        assert ExifTags.IFD.GPSInfo not in exif       # the default keeps the location out
        assert 274 not in exif                         # nor the orientation


def test_an_edited_copy_of_a_rw2_keeps_its_exif(tmp_path):
    from Imervue.image.in_place_save import save_edited_copy
    out = tmp_path / "P1_upscaled.png"
    save_edited_copy(_rw2(tmp_path / "P1.RW2"), Image.new("RGB", (8, 8)), out)
    with Image.open(out) as saved:
        exif = saved.getexif()
        assert (exif[272], exif.get_ifd(ExifTags.IFD.Exif)[0x9003]) == ("DMC-GX7", _TAKEN)
        assert min(exif) >= 0x00FE     # no Panasonic private tags, no embedded JPEG


def test_metadata_export_fills_the_camera_fields_of_an_orf(tmp_path, monkeypatch):
    from Imervue.library import metadata_export
    monkeypatch.setattr(metadata_export, "image_dimensions", lambda _p: (4608, 3456))
    rec: dict = {}
    metadata_export._populate_image_fields(str(_orf(tmp_path / "P1.ORF")), rec)  # noqa: SLF001
    assert rec["exif_Model"] == "E-M10"
    assert rec["exif_DateTimeOriginal"] == _TAKEN


# ---------------------------------------------------------------------------
# raw_xmp: the packet a camera keeps its in-camera rating in
# ---------------------------------------------------------------------------

_XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")
_PACKET = (b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
           b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           b'<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
           b'<xmp:Rating>4</xmp:Rating></rdf:Description></rdf:RDF></x:xmpmeta>'
           + b" " * 200 + b'<?xpacket end="w"?>')


def _cr3_with_xmp(path, packet=_PACKET):
    _cr3(path)
    data = path.read_bytes()
    path.write_bytes(data + _box(b"uuid", _XMP_UUID + packet))
    return path


def _orf_with_xmp(path):
    tiff = _with_exif_ifd({271: "OLYMPUS", 272: "E-M10", 700: _PACKET}, {0x9003: _TAKEN})
    path.write_bytes(b"IIRO" + tiff[4:])
    return path


def _raf_with_xmp(path):
    jpeg = io.BytesIO()
    Image.new("RGB", (16, 8)).save(jpeg, "JPEG", xmp=_PACKET)
    header = b"FUJIFILMCCD-RAW 0201FF383501".ljust(84, b"\0") + struct.pack(">II", 148, len(jpeg.getvalue()))
    path.write_bytes(header.ljust(148, b"\0") + jpeg.getvalue())
    return path


@pytest.mark.parametrize(("make", "name"), [
    (_cr3_with_xmp, "IMG_1.CR3"), (_orf_with_xmp, "P1.ORF"), (_raf_with_xmp, "DSCF1.RAF"),
])
def test_raw_xmp_finds_the_packet(tmp_path, make, name):
    packet = raw_xmp(make(tmp_path / name))
    assert b"<xmp:Rating>4</xmp:Rating>" in packet


@pytest.mark.parametrize(("make", "name"), [
    (_cr3, "IMG_1.CR3"), (_orf, "P1.ORF"), (_raf, "DSCF1.RAF"), (_rw2, "P1.RW2"),
])
def test_raw_xmp_without_a_packet_is_none(tmp_path, make, name):
    assert raw_xmp(make(tmp_path / name)) is None


def test_raw_xmp_of_another_format_is_none(tmp_path):
    path = tmp_path / "a.jpg"
    Image.new("RGB", (4, 4)).save(path, xmp=_PACKET)
    assert raw_xmp(path) is None


@pytest.mark.parametrize(("make", "name"), [
    (_cr3_with_xmp, "IMG_1.CR3"), (_orf_with_xmp, "P1.ORF"), (_raf_with_xmp, "DSCF1.RAF"),
])
def test_an_in_camera_rating_shows(tmp_path, make, name):
    """Rated on the camera, a CR3 / ORF / RAF showed no stars: Pillow can't open it."""
    from Imervue.image import xmp_sidecar
    assert xmp_sidecar.load(str(make(tmp_path / name))).rating == 4


def test_an_exif_rating_of_a_cr3_fills_in(tmp_path):
    from Imervue.image import xmp_sidecar
    path = tmp_path / "IMG_1.CR3"
    boxes = _box(b"CMT1", _tiff({271: "Canon", 272: "Canon EOS R6", 0x4746: 3}))
    moov = _box(b"moov", _box(b"uuid", _CANON_UUID + boxes))
    path.write_bytes(_box(b"ftyp", b"crx ") + moov)
    assert xmp_sidecar.load(str(path)).rating == 3


def test_a_missing_raw_has_no_embedded_metadata(tmp_path):
    from Imervue.image import xmp_sidecar
    assert xmp_sidecar.load(str(tmp_path / "gone.cr3")).is_empty()
    with pytest.raises(OSError):
        raw_xmp(tmp_path / "gone.orf")


def test_cr3_xmp_in_an_extended_size_box(tmp_path):
    path = tmp_path / "extended.cr3"
    payload = _XMP_UUID + _PACKET
    path.write_bytes(struct.pack(">I4sQ", 1, b"uuid", 16 + len(payload)) + payload)
    assert raw_xmp(path) == _PACKET


@pytest.mark.parametrize("size", [8, 16, 23])
def test_cr3_xmp_box_smaller_than_its_uuid_header_is_ignored(tmp_path, size):
    path = tmp_path / "broken.cr3"
    path.write_bytes(struct.pack(">I4s", size, b"uuid") + _XMP_UUID + _PACKET)
    assert raw_xmp(path) is None


@pytest.mark.parametrize("extension", [".orf", ".rw2", ".rwl"])
@pytest.mark.parametrize("big_endian", [False, True])
def test_tiff_raw_xmp_without_an_exif_sub_ifd(tmp_path, extension, big_endian):
    path = tmp_path / f"packet{extension}"
    tiff = _tiff({700: _PACKET}, big_endian=big_endian)
    magic = (b"OR" if big_endian else b"RO") if extension == ".orf" else (b"\x00U" if big_endian else b"U\x00")
    path.write_bytes(tiff[:2] + magic + tiff[4:])
    assert raw_xmp(path) == _PACKET


@pytest.mark.parametrize("count", [1, 2])
def test_a_tiff_raw_xmp_tag_with_the_wrong_type_is_ignored(tmp_path, count):
    path = tmp_path / "invalid.orf"
    # A corrupt tag 700 encoded as SHORT instead of a byte packet.
    path.write_bytes(b"IIRO" + struct.pack("<IH", 8, 1)
                     + struct.pack("<HHIHHI", 700, 3, count, 17, 18, 0))
    assert raw_xmp(path) is None


def test_cr3_xmp_in_a_truncated_box_is_ignored(tmp_path):
    path = tmp_path / "truncated.cr3"
    data = _box(b"uuid", _XMP_UUID + _PACKET)
    path.write_bytes(data[:-1])
    assert raw_xmp(path) is None


@pytest.mark.parametrize("extension", sorted(RAW_EXIF_EXTENSIONS))
def test_damaged_raw_xmp_is_ignored(tmp_path, extension):
    path = tmp_path / f"damaged{extension}"
    path.write_bytes(b"FUJIFILMCCD-RAW " if extension == ".raf" else b"broken")
    assert raw_xmp(path) is None


def test_cr3_xmp_size_limit_and_unrelated_uuid(tmp_path, monkeypatch):
    from Imervue.image import raw_exif as module

    path = tmp_path / "bounded.cr3"
    path.write_bytes(_box(b"uuid", b"x" * 16 + b"other metadata")
                     + _box(b"uuid", _XMP_UUID + _PACKET))
    monkeypatch.setattr(module, "_MAX_METADATA_BYTES", len(_PACKET))
    assert raw_xmp(path) == _PACKET
    monkeypatch.setattr(module, "_MAX_METADATA_BYTES", len(_PACKET) - 1)
    assert raw_xmp(path) is None


def test_empty_cr3_xmp_is_none(tmp_path):
    assert raw_xmp(_cr3_with_xmp(tmp_path / "empty.cr3", packet=b"")) is None


@pytest.mark.parametrize("packet", [_PACKET, b"not XML",
                                  b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///no-file">]><x>&e;</x>'])
def test_raw_xmp_rating_precedes_exif_and_bad_xml_falls_back(tmp_path, packet):
    from Imervue.image import xmp_sidecar

    path = tmp_path / "rated.cr3"
    boxes = _box(b"CMT1", _tiff({0x4749: 50}))  # EXIF RatingPercent: three stars
    path.write_bytes(_box(b"moov", _box(b"uuid", _CANON_UUID + boxes))
                     + _box(b"uuid", _XMP_UUID + packet))
    assert xmp_sidecar.load(path).rating == (4 if packet == _PACKET else 3)


def test_a_sidecar_rating_precedes_the_camera_rating(tmp_path):
    from Imervue.image import xmp_sidecar

    path = _cr3_with_xmp(tmp_path / "rated.cr3")
    xmp_sidecar.save(path, xmp_sidecar.XmpData(rating=1))
    assert xmp_sidecar.load(path).rating == 1
