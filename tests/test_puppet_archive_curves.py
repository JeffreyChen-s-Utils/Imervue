"""Archive contracts shared by drawable curves and named animation entries."""
import copy
import io
import json
import zipfile

import pytest

from Imervue.puppet.document_io import PuppetFormatError, from_zip_bytes, to_zip_bytes


def _archive(*, drawable=None, **entries):
    manifest = {
        "version": 1, "size": [32, 32], "deformers": [], "parameters": [],
        "drawables": [] if drawable is None else [drawable],
    }
    manifest.update(entries.pop("manifest", {}))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("puppet.json", json.dumps(manifest))
        for name, data in entries.items():
            archive.writestr(name, json.dumps(data))
    return stream.getvalue()


def _drawable():
    return {
        "id": "face", "texture": "textures/face.png", "vertices": [[0, 0]],
        "uvs": [[0, 0]], "indices": [], "draw_order": 0,
    }


@pytest.mark.parametrize("field,value_key,value", [
    ("opacity_keys", "alpha", "0.25"),
    ("multiply_color_keys", "color", ["0.5", "0.75", "1"]),
])
@pytest.mark.parametrize("fault", ["entry", "parameter", "stops", "stop"])
def test_curve_errors_identify_field_entry_and_stop(field, value_key, value, fault):
    entry = {"parameter": "P", "stops": [
        {"value": -1, value_key: value}, {"value": 1, value_key: value},
    ]}
    broken = copy.deepcopy(entry)
    suffix = {"entry": "must be a dict", "parameter": "missing 'parameter'",
              "stops": "needs >=2 stops", "stop": f"must have 'value' and '{value_key}'"}
    if fault == "entry":
        broken = None
    elif fault == "parameter":
        broken["parameter"] = ""
    elif fault == "stops":
        broken["stops"] = []
    else:
        del broken["stops"][1][value_key]
    drawable = _drawable()
    drawable[field] = [entry, broken]
    with pytest.raises(PuppetFormatError) as error:
        from_zip_bytes(_archive(drawable=drawable))
    location = f"{field}[1]" + (".stops[1]" if fault == "stop" else "")
    assert str(error.value) == f"drawable 'face' {location} {suffix[fault]}"


def test_both_curve_types_round_trip_without_crossing_values_or_mutating_source():
    drawable = _drawable()
    drawable["opacity_keys"] = [{"parameter": "Opacity", "stops": [
        {"value": "-1", "alpha": "0.25"}, {"value": "1", "alpha": "0.75"},
    ]}]
    drawable["multiply_color_keys"] = [{"parameter": "Tint", "stops": [
        {"value": "-2", "color": ["1", "0.5", "0"]},
        {"value": "2", "color": ["0", "0.25", "1"]},
    ]}]
    document = from_zip_bytes(_archive(drawable=drawable))
    before = copy.deepcopy(document.drawables[0])
    encoded = to_zip_bytes(document)
    with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
        saved = json.loads(archive.read("puppet.json"))["drawables"][0]
    assert saved["opacity_keys"][0]["stops"] == [
        {"value": -1.0, "alpha": 0.25}, {"value": 1.0, "alpha": 0.75},
    ]
    assert saved["multiply_color_keys"][0]["stops"] == [
        {"value": -2.0, "color": [1.0, 0.5, 0.0]},
        {"value": 2.0, "color": [0.0, 0.25, 1.0]},
    ]
    assert from_zip_bytes(encoded).drawables[0] == before
    assert document.drawables[0] == before


@pytest.mark.parametrize("field,label,payload", [
    ("motions", "motion", {"duration": 1, "tracks": []}),
    ("expressions", "expression", {"params": []}),
])
def test_named_entries_keep_manifest_order_and_duplicates(field, label, payload):
    names = ["second", "first", "second"]
    entries = {f"{field}/{name}.json": payload for name in names}
    document = from_zip_bytes(_archive(manifest={field: names}, **entries))
    loaded = getattr(document, field)
    assert [entry.name for entry in loaded] == names
    assert loaded[0] is not loaded[2]
    del entries[f"{field}/first.json"]
    with pytest.raises(PuppetFormatError) as error:
        from_zip_bytes(_archive(manifest={field: names}, **entries))
    assert str(error.value) == f"{label} 'first' listed but {field}/first.json missing"
