"""Tests for the XMP sidecar dialog's batch import / export."""
from __future__ import annotations

from PIL import Image

from Imervue.gui.xmp_sidecar_dialog import run_export, run_import
from Imervue.image import xmp_sidecar
from Imervue.user_settings.user_setting_dict import user_setting_dict

_PACKET = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
           b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
           b'rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:Rating="4"/>'
           b'</rdf:RDF></x:xmpmeta>')


def _jpeg(tmp_path, name, **kwargs):
    path = tmp_path / name
    Image.new("RGB", (8, 8)).save(path, **kwargs)
    return str(path)


def test_import_takes_sidecars_and_metadata_inside_the_file(tmp_path):
    """A JPEG Lightroom rated (XMP inside the file, no sidecar) counted as missing."""
    with_sidecar = _jpeg(tmp_path, "a.jpg")
    xmp_sidecar.save(with_sidecar, xmp_sidecar.XmpData(rating=2))
    embedded = _jpeg(tmp_path, "b.jpg", xmp=_PACKET)
    plain = _jpeg(tmp_path, "c.jpg")
    assert run_import([with_sidecar, embedded, plain]) == (2, 1, 0)
    assert user_setting_dict["image_ratings"] == {with_sidecar: 2, embedded: 4}


def test_an_empty_sidecar_still_counts_as_imported(tmp_path):
    photo = _jpeg(tmp_path, "a.jpg")
    xmp_sidecar.sidecar_path_for(photo).write_text(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"/>', encoding="utf-8")
    user_setting_dict["image_ratings"] = {photo: 5}
    assert run_import([photo]) == (1, 0, 0)
    assert photo not in user_setting_dict["image_ratings"]     # the sidecar says unrated


def test_import_counts_a_failure_and_carries_on(tmp_path, monkeypatch):
    first, second = _jpeg(tmp_path, "a.jpg", xmp=_PACKET), _jpeg(tmp_path, "b.jpg", xmp=_PACKET)

    def refuse_first(path, data):
        if path == first:
            raise OSError("settings locked")
        user_setting_dict.setdefault("image_ratings", {})[path] = data.rating

    monkeypatch.setattr(xmp_sidecar, "apply_to_settings", refuse_first)
    assert run_import([first, second]) == (1, 0, 1)


def test_export_writes_what_has_data_and_skips_the_rest(tmp_path):
    rated, unrated = _jpeg(tmp_path, "a.jpg"), _jpeg(tmp_path, "b.jpg")
    user_setting_dict["image_ratings"] = {rated: 3}
    assert run_export([rated, unrated]) == (1, 1, 0)
    assert xmp_sidecar.has_sidecar(rated) and not xmp_sidecar.has_sidecar(unrated)
