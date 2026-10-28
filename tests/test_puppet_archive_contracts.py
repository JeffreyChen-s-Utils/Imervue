"""Public archive contracts across manifest and drawable format boundaries."""
import io
import json
import zipfile

import pytest

from Imervue.puppet.document_io import PuppetFormatError, from_zip_bytes, to_zip_bytes
from test_puppet_archive_curves import _archive, _drawable


@pytest.mark.parametrize("field", ["drawables", "deformers", "parameters"])
@pytest.mark.parametrize("invalid", [None, {}, "", 0])
def test_required_manifest_collections_keep_field_specific_errors(field, invalid):
    with pytest.raises(PuppetFormatError) as error:
        from_zip_bytes(_archive(manifest={field: invalid}))
    assert str(error.value) == f"manifest key {field!r} must be a list"


@pytest.mark.parametrize("field", ["hit_areas", "parameter_blends", "parts"])
@pytest.mark.parametrize("empty", [None, [], {}, "", 0, False])
def test_optional_manifest_collections_keep_empty_input_and_omission_rules(field, empty):
    document = from_zip_bytes(_archive(manifest={field: empty}))
    assert getattr(document, field) == []
    with zipfile.ZipFile(io.BytesIO(to_zip_bytes(document))) as archive:
        assert field not in json.loads(archive.read("puppet.json"))


def test_manifest_collections_keep_order_duplicates_and_json_field_order():
    document = from_zip_bytes(_archive(manifest={
        "hit_areas": [{"id": "touch", "drawables": []}] * 2,
        "parameter_blends": [{"id": "blend", "parameters": ["P"], "keys": []}],
        "parts": [{"id": "last"}, {"id": "first"}, {"id": "last"}],
        "display_names": {"P": "Parameter"},
    }))
    assert [part.id for part in document.parts] == ["last", "first", "last"]
    assert document.parts[0] is not document.parts[2]
    encoded = to_zip_bytes(document)
    with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
        manifest = json.loads(archive.read("puppet.json"))
    assert list(manifest) == [
        "$schema", "version", "size", "drawables", "deformers", "parameters",
        "hit_areas", "parameter_blends", "parts", "display_names",
    ]
    assert from_zip_bytes(encoded) == document


@pytest.mark.parametrize("field", ["opacity_keys", "multiply_color_keys", "vertex_morphs"])
@pytest.mark.parametrize("entry", [None, {}, {"parameter": 12}, {"parameter": ""}])
def test_parameter_curve_and_morph_errors_keep_their_domain_location(field, entry):
    drawable = _drawable()
    drawable[field] = [entry]
    with pytest.raises(PuppetFormatError) as error:
        from_zip_bytes(_archive(drawable=drawable))
    detail = "must be a dict" if entry is None else "missing 'parameter'"
    assert str(error.value) == f"drawable 'face' {field}[0] {detail}"


def test_morph_endpoint_conversion_keeps_tuple_storage_and_json_lists():
    drawable = _drawable()
    drawable["vertex_morphs"] = [{
        "parameter": "P", "delta_at_min": [["-1", "2.5"]], "delta_at_max": None,
    }]
    document = from_zip_bytes(_archive(drawable=drawable))
    morph = document.drawables[0].vertex_morphs[0]
    assert morph == {"parameter": "P", "delta_at_min": [(-1.0, 2.5)], "delta_at_max": []}
    encoded = to_zip_bytes(document)
    with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
        saved = json.loads(archive.read("puppet.json"))["drawables"][0]["vertex_morphs"][0]
    assert saved == {"parameter": "P", "delta_at_min": [[-1.0, 2.5]], "delta_at_max": []}
    assert from_zip_bytes(encoded) == document
