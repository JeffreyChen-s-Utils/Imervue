"""Contracts for the XMP sidecar format: exact written text, round-trips and parse edge cases."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("defusedxml")

from PIL import Image  # noqa: E402

from Imervue.image import xmp_sidecar  # noqa: E402
from Imervue.image.xmp_sidecar import XmpData  # noqa: E402

_PUBLIC_NAMES = (
    "XmpData", "UnreadableSidecarError", "sidecar_path_for", "has_sidecar", "label_color",
    "load", "load_embedded", "save", "snapshot_from_settings", "apply_to_settings",
    "export_for", "import_for",
)

_NEW_SIDECAR = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:dc="http://purl.org/dc/elements/1.1/" \
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:x="adobe:ns:meta/" \
xmlns:xmp="http://ns.adobe.com/xap/1.0/" x:xmptk="Imervue XMP">
  <rdf:RDF>
    <rdf:Description rdf:about="" xmp:Rating="4" xmp:Label="Red">
      <dc:title>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">T &amp; &lt;t&gt;</rdf:li>
        </rdf:Alt>
      </dc:title>
      <dc:description>
        <rdf:Alt>
          <rdf:li xml:lang="x-default">D</rdf:li>
        </rdf:Alt>
      </dc:description>
      <dc:subject>
        <rdf:Bag>
          <rdf:li>k1</rdf:li>
          <rdf:li>k2</rdf:li>
        </rdf:Bag>
      </dc:subject>
      <dc:creator>
        <rdf:Seq>
          <rdf:li>Ann</rdf:li>
        </rdf:Seq>
      </dc:creator>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

_FOREIGN_SIDECAR = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" '
    'xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" '
    'xmlns:xmp="http://ns.adobe.com/xap/1.0/" crs:Exposure2012="+0.50" xmp:Rating="2">'
    "<xmp:Label>Select</xmp:Label></rdf:Description></rdf:RDF></x:xmpmeta>"
)

_MERGED_SIDECAR = """<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" \
xmlns:dc="http://purl.org/dc/elements/1.1/" \
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:x="adobe:ns:meta/" \
xmlns:xmp="http://ns.adobe.com/xap/1.0/">
  <rdf:RDF>
    <rdf:Description rdf:about="" crs:Exposure2012="+0.50" xmp:Rating="5" xmp:Label="Select">
      <dc:subject>
        <rdf:Bag>
          <rdf:li>a</rdf:li>
        </rdf:Bag>
      </dc:subject>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

_RDF = 'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
_DC = 'xmlns:dc="http://purl.org/dc/elements/1.1/"'


def _write_xmp(path: Path, body: str) -> None:
    path.with_suffix(".xmp").write_text(
        f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF {_RDF}>{body}</rdf:RDF></x:xmpmeta>',
        encoding="utf-8")


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "a.jpg"
    path.write_bytes(b"x")
    return path


def test_every_public_name_stays_importable_from_the_module():
    for name in _PUBLIC_NAMES:
        assert hasattr(xmp_sidecar, name), name


def test_a_new_sidecar_is_written_exactly(photo):
    data = XmpData(rating=4, title="T & <t>", description="D", keywords=["k1", "", "k2"],
                   color_label="Red", creator="Ann")
    assert xmp_sidecar.save(photo, data) == photo.with_suffix(".xmp")
    assert photo.with_suffix(".xmp").read_text(encoding="utf-8") == _NEW_SIDECAR


def test_a_merge_into_a_foreign_sidecar_is_written_exactly(photo):
    photo.with_suffix(".xmp").write_text(_FOREIGN_SIDECAR, encoding="utf-8")
    xmp_sidecar.save(photo, XmpData(rating=5, keywords=["a"], color_label="Select"))
    assert photo.with_suffix(".xmp").read_text(encoding="utf-8") == _MERGED_SIDECAR


def test_write_then_read_round_trips_every_written_field(photo):
    data = XmpData(rating=-1, title="Title", description="Desc", keywords=["x", "y"],
                   color_label="Approved", creator="Bo")
    xmp_sidecar.save(photo, data)
    assert xmp_sidecar.load(photo) == data


def test_saving_the_same_data_twice_gives_the_same_bytes(photo):
    data = XmpData(rating=3, keywords=["k"], creator="C")
    xmp_sidecar.save(photo, data)
    first = photo.with_suffix(".xmp").read_bytes()
    xmp_sidecar.save(photo, data)
    assert photo.with_suffix(".xmp").read_bytes() == first


def test_saving_empty_data_without_a_sidecar_writes_nothing(photo):
    assert xmp_sidecar.save(photo, XmpData()) == photo.with_suffix(".xmp")
    assert not photo.with_suffix(".xmp").exists()


def test_a_sidecar_without_rdf_gets_an_rdf_and_a_description(photo):
    photo.with_suffix(".xmp").write_text(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:o="urn:other"><o:keep>1</o:keep></x:xmpmeta>',
        encoding="utf-8")
    xmp_sidecar.save(photo, XmpData(rating=2))
    text = photo.with_suffix(".xmp").read_text(encoding="utf-8")
    assert "<o:keep>1</o:keep>" in text
    assert '<rdf:Description rdf:about="" xmp:Rating="2" />' in text
    assert xmp_sidecar.load(photo).rating == 2


def test_a_reserved_prefix_in_the_file_does_not_break_a_save(photo):
    photo.with_suffix(".xmp").write_text(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:ns0="urn:zero"><ns0:k>1</ns0:k></x:xmpmeta>',
        encoding="utf-8")
    xmp_sidecar.save(photo, XmpData(rating=1))
    assert xmp_sidecar.load(photo).rating == 1


@pytest.mark.parametrize(("raw", "expected"), [
    ("3.9", 3), ("9", 5), ("-7", -1), ("abc", 0), ("", 0),
])
def test_a_rating_attribute_is_truncated_and_clamped(photo, raw, expected):
    _write_xmp(photo, f'<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
                      f'xmp:Rating="{raw}"/>')
    assert xmp_sidecar.load(photo).rating == expected


def test_a_rating_and_label_in_element_form_are_read(photo):
    _write_xmp(photo, '<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
                      '<xmp:Rating>4</xmp:Rating><xmp:Label>  Blue </xmp:Label>'
                      '</rdf:Description>')
    data = xmp_sidecar.load(photo)
    assert (data.rating, data.color_label) == (4, "Blue")


@pytest.mark.parametrize(("items", "expected"), [
    ('<rdf:li xml:lang="de">Hallo</rdf:li><rdf:li xml:lang="x-default"> Hi </rdf:li>', "Hi"),
    ('<rdf:li xml:lang="de"> Hallo </rdf:li><rdf:li xml:lang="fr">Salut</rdf:li>', "Hallo"),
    ('<rdf:li>Plain</rdf:li>', "Plain"),
    ("", ""),
])
def test_the_title_takes_the_default_language_else_the_first(photo, items, expected):
    _write_xmp(photo, f'<rdf:Description {_DC}><dc:title><rdf:Alt>{items}</rdf:Alt>'
                      '</dc:title></rdf:Description>')
    assert xmp_sidecar.load(photo).title == expected


def test_a_title_without_alt_is_its_text(photo):
    _write_xmp(photo, f'<rdf:Description {_DC}><dc:title> Bare </dc:title></rdf:Description>')
    assert xmp_sidecar.load(photo).title == "Bare"


def test_keywords_in_a_seq_are_read_and_blank_entries_skipped(photo):
    _write_xmp(photo, f'<rdf:Description {_DC}><dc:subject><rdf:Seq><rdf:li> a </rdf:li>'
                      '<rdf:li> </rdf:li><rdf:li>b</rdf:li></rdf:Seq></dc:subject>'
                      '<dc:creator><rdf:Seq><rdf:li>First</rdf:li><rdf:li>Second</rdf:li>'
                      '</rdf:Seq></dc:creator></rdf:Description>')
    data = xmp_sidecar.load(photo)
    assert (data.keywords, data.creator) == (["a", "b"], "First")


def test_a_bare_description_root_is_read(photo):
    photo.with_suffix(".xmp").write_text(
        f'<rdf:Description {_RDF} xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:Rating="3"/>',
        encoding="utf-8")
    assert xmp_sidecar.load(photo).rating == 3


def test_a_document_without_description_reads_empty(photo):
    photo.with_suffix(".xmp").write_text('<x:xmpmeta xmlns:x="adobe:ns:meta/"/>',
                                         encoding="utf-8")
    assert xmp_sidecar.load(photo) == XmpData()


@pytest.mark.parametrize(("exif", "stars"), [
    ({0x4746: 9}, 5), ({0x4746: -3}, 0), ({0x4749: 75}, 4), ({0x4746: 2, 0x4749: 99}, 2),
])
def test_the_embedded_exif_rating_is_clamped(tmp_path, exif, stars):
    path = tmp_path / "e.jpg"
    image = Image.new("RGB", (4, 4))
    exif_block = image.getexif()
    for tag, value in exif.items():
        exif_block[tag] = value
    image.save(path, exif=exif_block)
    assert xmp_sidecar.load_embedded(path).rating == stars


def test_an_embedded_text_packet_is_read(tmp_path, monkeypatch):
    path = tmp_path / "p.png"
    Image.new("RGB", (2, 2)).save(path)
    packet = (f'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF {_RDF}><rdf:Description {_DC}>'
              '<dc:subject><rdf:Bag><rdf:li>k</rdf:li></rdf:Bag></dc:subject>'
              '</rdf:Description></rdf:RDF></x:xmpmeta>')

    class _TextPacketImage:
        info = {"xmp": packet}

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def getexif(self):
            return {}

    monkeypatch.setattr(Image, "open", lambda *_a, **_k: _TextPacketImage())
    assert xmp_sidecar.load_embedded(path).keywords == ["k"]


def test_label_mapping_for_write_keeps_or_replaces_the_word():
    from Imervue.image.xmp_sidecar import _label_to_write
    assert _label_to_write("red", "Select") == "Select"
    assert _label_to_write("blue", "Select") == "Blue"
    assert _label_to_write(None, "Custom") == "Custom"
    assert _label_to_write(None, "Red") == ""
    assert xmp_sidecar.label_color(" TO DO ") == "purple"
    assert xmp_sidecar.label_color("Custom") is None
