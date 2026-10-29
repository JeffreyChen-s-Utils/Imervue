"""Contract tests for ``cubism_native_convert``.

They pin, on a small synthetic rig, everything the native ``.moc3``
conversion produces: the serialised ``.puppet`` archive, the exact
sequence of calls made on the native model, the log records, and the
errors raised. The Cubism Core DLL is not redistributable, so a fake
model stands in for :class:`CubismModel` and the loaders are patched
where :func:`cubism_to_puppet` looks them up.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import zipfile
from pathlib import Path
from typing import cast

import pytest

from Imervue.puppet import cubism_native_convert
from Imervue.puppet.cubism_native_bridge import (
    CubismBridgeError,
    CubismModel,
    DrawableInfo,
    ParameterInfo,
)
from Imervue.puppet.document_io import load_puppet, to_zip_bytes

_LOGGER_NAME = "Imervue.plugin.puppet.cubism_native_convert"
_TMP = "<TMP>"


def _drawable(index: int, **overrides) -> DrawableInfo:
    values = {
        "id": f"D{index}", "texture_index": 0, "draw_order": 500,
        "render_order": index, "is_visible": True, "opacity": 1.0,
        "blend_mode": 0, "constant_flags": 0, "vertex_count": 2,
        "index_count": 3, "positions": [0.0, 0.0, 1.0, 1.0],
        "uvs": [0.0, 0.25, 1.0, 0.75], "indices": [0, 1, 0],
        "mask_drawable_indices": [],
    }
    values.update(overrides)
    return DrawableInfo(**values)


class _FakeModel:
    """Scripted stand-in for :class:`CubismModel` that logs every call."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.params = [
            ParameterInfo(id="P0", minimum=-1.0, maximum=1.0, default=0.0),
            ParameterInfo(id="P1", minimum=0.0, maximum=0.0, default=0.0),
            ParameterInfo(id="P2", minimum=0.0, maximum=1.0, default=0.0),
        ]
        self.rest = [
            _drawable(0, mask_drawable_indices=[1, 2]),
            _drawable(1, texture_index=5, is_visible=False, opacity=0.0,
                      blend_mode=1),
            _drawable(2, texture_index=-1, blend_mode=7, opacity=0.5),
        ]
        self.values = [p.default for p in self.params]

    def canvas_info(self) -> dict[str, float]:
        self.calls.append(("canvas_info",))
        return {"width": 100.4, "height": 50.6, "origin_x": 50.0,
                "origin_y": 25.0, "pixels_per_unit": 10.0}

    def parameters(self) -> list[ParameterInfo]:
        self.calls.append(("parameters",))
        return list(self.params)

    def drawables(self) -> list[DrawableInfo]:
        self.calls.append(("drawables",))
        return list(self.rest)

    def set_parameter_values(self, values: list[float]) -> None:
        self.calls.append(("set_parameter_values", tuple(values)))
        self.values = list(values)

    def update(self) -> None:
        self.calls.append(("update",))

    def vertex_positions(self) -> list[list[float]]:
        self.calls.append(("vertex_positions",))
        p0, _p1, p2 = self.values
        d0 = [0.5 * p0, 0.0, 1.0 + 0.5 * p0, 1.0 - 0.25 * p0]
        d1 = [1e-6 * p0, 0.0, 1.0, 1.0]
        # D2 reports a short array while P0 moves: the morph is dropped.
        d2 = [0.0, 0.1 * p2] if p0 else [0.0, 0.1 * p2, 1.0, 1.0 + 0.25 * p2]
        return [d0, d1, d2]

    def visibility_flags(self) -> list[bool]:
        self.calls.append(("visibility_flags",))
        p0, _p1, p2 = self.values
        return [p0 >= 0, p2 == 1.0, True]


def _write(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


def _motion3(param_id: str = "P0") -> dict:
    return {
        "Version": 3,
        "Meta": {"Duration": 1.0, "Fps": 30, "Loop": False},
        "Curves": [{"Target": "Parameter", "Id": param_id,
                    "Segments": [0.0, 0.0, 0, 1.0, 1.0]}],
    }


def _build_bundle_dir(base: Path) -> dict:
    """Lay out a bundle that hits every branch of the converter."""
    (base / "tex").mkdir()
    (base / "tex" / "atlas.png").write_bytes(b"PNGDATA")
    _write(base / "motions" / "tap.motion3.json", _motion3())
    _write(base / "motions" / "orphan.motion3.json", _motion3("P2"))
    _write(base / "other" / "wave.motion3.json", _motion3())
    _write(base / "exp" / "smile.exp3.json", {
        "Type": "Live2D Expression",
        "Parameters": [{"Id": "P0", "Value": 0.5, "Blend": "Add"}],
    })
    _write(base / "bad.exp3.json", {"Type": "Something Else"})
    _write(base / "model.physics3.json", {"PhysicsSettings": [{
        "Id": "Hair", "Input": [{"Source": {"Target": "Parameter", "Id": "P0"}}],
        "Output": [{"Destination": {"Target": "Parameter", "Id": "P2"}}],
        "Vertices": [{"Position": {"X": 0, "Y": 0}, "Mobility": 1,
                      "Delay": 1, "Acceleration": 1, "Radius": 0},
                     {"Position": {"X": 0, "Y": 3}, "Mobility": 0.9,
                      "Delay": 0.8, "Acceleration": 1.5, "Radius": 3}],
    }]})
    _write(base / "model.cdi3.json", "{not json")
    return {
        "Version": 3,
        "FileReferences": {
            "Moc": "model.moc3",
            "Textures": ["tex/atlas.png", "tex/missing.png"],
            "Motions": {
                "Tap": [
                    {"File": "motions/tap.motion3.json", "FadeInTime": 0.2,
                     "FadeOutTime": 1, "Sound": "sounds/tap.wav"},
                    "not-a-dict",
                    {"File": ""},
                    {"File": "motions/gone.motion3.json"},
                ],
                "Wave": [{"File": "other/wave.motion3.json",
                          "FadeInTime": "slow"}],
                "Empty": None,
            },
            "Expressions": [
                {"Name": "Smile", "File": "smile.exp3.json"},
                {"File": "bad.exp3.json"},
                {"Name": "Ghost", "File": "ghost.exp3.json"},
                {"Name": "NoFile"},
                7,
            ],
            "Physics": "model.physics3.json",
            "DisplayInfo": "model.cdi3.json",
        },
        "HitAreas": [
            {"Id": "D0", "Name": "Head"},
            {"Id": "D2"},
            {"Id": ""},
            {"Name": "NoId"},
            "nope",
        ],
    }


def _normalise(value, tmp: str):
    if isinstance(value, dict):
        return {k: _normalise(v, tmp) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise(v, tmp) for v in value]
    if isinstance(value, str):
        return value.replace(tmp, _TMP).replace("\\", "/")
    return value


def _archive_view(document, tmp: Path) -> dict:
    """Decode the serialised archive into a path-independent dict."""
    out: dict = {}
    with zipfile.ZipFile(io.BytesIO(to_zip_bytes(document))) as zf:
        for name in zf.namelist():
            data = zf.read(name)
            if name.endswith(".json"):
                out[name] = _normalise(json.loads(data), str(tmp))
            else:
                out[name] = hashlib.sha256(data).hexdigest()
    return out


def _digest(view: dict) -> str:
    blob = json.dumps(view, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@pytest.fixture
def converted(tmp_path, monkeypatch, caplog):
    """Run the whole conversion through the fake model."""
    manifest = _build_bundle_dir(tmp_path)
    _write(tmp_path / "model.model3.json", manifest)
    model = _FakeModel()
    seen: dict = {}

    def fake_library(dll_path):
        seen["dll"] = dll_path
        return "LIB"

    def fake_model_file(lib, moc_path):
        seen["model_file"] = (lib, moc_path)
        return model

    monkeypatch.setattr(cubism_native_convert, "load_library", fake_library)
    monkeypatch.setattr(cubism_native_convert, "load_model_file", fake_model_file)
    caplog.set_level(logging.DEBUG, logger=_LOGGER_NAME)
    out = tmp_path / "out.puppet"
    document = cubism_native_convert.cubism_to_puppet(
        tmp_path / "model.model3.json", output_path=out, dll_path="core.dll",
    )
    records = [
        (r.name, r.levelname, _normalise(r.getMessage(), str(tmp_path)))
        for r in caplog.records if r.name == _LOGGER_NAME
    ]
    return {"document": document, "model": model, "seen": seen,
            "records": records, "out": out, "tmp": tmp_path}


def test_loaders_receive_the_dll_and_moc_paths(converted):
    seen, tmp = converted["seen"], converted["tmp"]
    assert seen["dll"] == "core.dll"
    assert seen["model_file"] == ("LIB", tmp / "model.moc3")


def test_native_call_sequence_is_pinned(converted):
    set_ = "set_parameter_values"
    expected = [
        ("canvas_info",), ("parameters",), ("drawables",),
        # Morph sweep: P0 min / max, P1 skipped, P2 min / max, restore.
        (set_, (-1.0, 0.0, 0.0)), ("update",), ("vertex_positions",),
        (set_, (1.0, 0.0, 0.0)), ("update",), ("vertex_positions",),
        (set_, (0.0, 0.0, 0.0)), ("update",), ("vertex_positions",),
        (set_, (0.0, 0.0, 1.0)), ("update",), ("vertex_positions",),
        (set_, (0.0, 0.0, 0.0)), ("update",),
        # Visibility sweep, same order, restore.
        (set_, (-1.0, 0.0, 0.0)), ("update",), ("visibility_flags",),
        (set_, (1.0, 0.0, 0.0)), ("update",), ("visibility_flags",),
        (set_, (0.0, 0.0, 0.0)), ("update",), ("visibility_flags",),
        (set_, (0.0, 0.0, 1.0)), ("update",), ("visibility_flags",),
        (set_, (0.0, 0.0, 0.0)), ("update",),
    ]
    assert converted["model"].calls == expected


def test_log_records_are_pinned(converted):
    tex = f"{_TMP}/tex/missing.png"
    gone = f"{_TMP}/motions/gone.motion3.json"
    bad = f"{_TMP}/bad.exp3.json"
    cdi = f"{_TMP}/model.cdi3.json"
    records = converted["records"]
    assert records[0] == (_LOGGER_NAME, "WARNING", f"texture {tex} missing on disk")
    assert records[1] == (_LOGGER_NAME, "INFO", f"motion {gone} missing — skipping")
    assert records[2][:2] == (_LOGGER_NAME, "INFO")
    assert records[2][2].startswith(f"expression {bad} failed: ")
    assert "Live2D Expression" in records[2][2]
    assert records[3] == (_LOGGER_NAME, "INFO", "expression ghost.exp3.json missing — skipping")
    assert records[4][:2] == (_LOGGER_NAME, "INFO")
    assert records[4][2].startswith(f"cdi {cdi} failed: ")
    assert len(records) == 5


def test_drawables_are_pinned(converted):
    d0, d1, d2 = converted["document"].drawables
    assert converted["document"].size == (100, 51)
    assert d0.vertices == [(50.0, 25.0), (60.0, 15.0)]
    assert d0.uvs == [(0.0, 0.75), (1.0, 0.25)]
    assert d0.texture == "textures/texture_00.png"
    assert d0.clip_mask == "D1"
    assert d0.blend_mode == "normal"
    assert d1.texture == ""
    assert d1.blend_mode == "additive"
    assert d2.texture == ""
    assert d2.blend_mode == "normal"
    assert d2.clip_mask is None
    assert [d.draw_order for d in (d0, d1, d2)] == [0, 1, 2]


def test_morphs_and_opacity_curves_are_pinned(converted):
    d0, d1, d2 = converted["document"].drawables
    assert d0.vertex_morphs == [{
        "parameter": "P0",
        "delta_at_min": [(-5.0, -0.0), (-5.0, -2.5)],
        "delta_at_max": [(5.0, -0.0), (5.0, 2.5)],
    }]
    assert d1.vertex_morphs is None
    assert d2.vertex_morphs == [{
        "parameter": "P2",
        "delta_at_min": [(0.0, -0.0), (0.0, -0.0)],
        "delta_at_max": [(0.0, -1.0), (0.0, -2.5)],
    }]
    assert d0.opacity_keys == [{"parameter": "P0", "stops": [
        {"value": -1.0, "alpha": 0.0}, {"value": 0.0, "alpha": 1.0},
        {"value": 1.0, "alpha": 1.0}]}]
    assert d1.opacity_keys == [{"parameter": "P2", "stops": [
        {"value": 0.0, "alpha": 0.0}, {"value": 0.0, "alpha": 0.0},
        {"value": 1.0, "alpha": 1.0}]}]
    assert (d1.visible, d1.opacity) == (True, 1.0)
    assert d2.opacity_keys is None
    assert d2.opacity == pytest.approx(0.5)


def test_bundle_contents_are_pinned(converted):
    document, tmp = converted["document"], converted["tmp"]
    assert list(document.textures) == ["textures/texture_00.png"]
    assert [p.id for p in document.parameters] == ["P0", "P1", "P2"]
    authored = [m for m in document.motions if not m.name.startswith("synth_")]
    assert [(m.name, m.group) for m in authored] == [
        ("Tap/tap", "Tap"), ("Wave/wave", "Wave"), ("orphan", "Idle"),
    ]
    tap, wave, orphan = authored
    assert tap.sound_path == str(tmp / "sounds/tap.wav")
    assert (tap.fade_in_duration, tap.fade_out_duration) == (0.2, 1.0)
    assert wave.sound_path is None
    assert (orphan.fade_in_duration, orphan.fade_out_duration) == (0.5, 0.5)
    assert [e.name for e in document.expressions] == ["Smile"]
    assert [r.id for r in document.physics_rigs] == ["Hair"]
    assert [(h.id, h.drawables) for h in document.hit_areas] == [
        ("Head", ["D0"]), ("D2", ["D2"]),
    ]


def test_serialised_archive_is_pinned(converted):
    view = _archive_view(converted["document"], converted["tmp"])
    assert sorted(view) == [
        "expressions/Smile.json", "mimetype",
        "motions/Tap/tap.json", "motions/Wave/wave.json",
        "motions/orphan.json", "physics.json", "puppet.json",
        "textures/texture_00.png",
    ]
    assert _digest(view) == (
        "497d5bb18b7803ad47ac04c6e9f5d3e09e9bb90329769183f9a32caa35b15144"
    )


def test_output_path_saves_the_same_document(converted):
    reloaded = load_puppet(converted["out"])
    original = _archive_view(converted["document"], converted["tmp"])
    assert _archive_view(reloaded, converted["tmp"]) == original


def test_synthetic_motions_fill_a_sparse_rig(monkeypatch):
    from Imervue.puppet import synth_motions
    from Imervue.puppet.document import Motion, PuppetDocument
    synth = Motion(name="synth_idle", duration=1.0)
    asked: list = []

    def fake_synth(document):
        asked.append(document)
        return [synth]

    monkeypatch.setattr(synth_motions, "synthesise_idle_motions", fake_synth)
    doc = PuppetDocument(size=(8, 8))
    doc.motions.extend(Motion(name=f"m{i}", duration=1.0) for i in range(3))
    cubism_native_convert._attach_synthetic_motions(doc)  # noqa: SLF001
    assert [m.name for m in doc.motions] == ["m0", "m1", "m2"]
    assert asked == []
    sparse = PuppetDocument(size=(8, 8))
    sparse.motions.extend(Motion(name=f"m{i}", duration=1.0) for i in range(2))
    cubism_native_convert._attach_synthetic_motions(sparse)  # noqa: SLF001
    assert [m.name for m in sparse.motions] == ["m0", "m1", "synth_idle"]
    assert asked == [sparse]


def test_missing_moc_reference_message(tmp_path):
    model = _write(tmp_path / "m.model3.json", {"FileReferences": {"Moc": ""}})
    with pytest.raises(CubismBridgeError) as info:
        cubism_native_convert.cubism_to_puppet(model)
    assert str(info.value) == f"{model}: FileReferences.Moc is missing"


def test_canvas_transform_round_numbers():
    transform = cubism_native_convert._CanvasTransform.from_canvas_info(  # noqa: SLF001
        {"pixels_per_unit": 0.0})
    assert transform.pixels_per_unit == 1.0
    assert transform.position(2.0, 3.0) == (2.0, -3.0)
    assert transform.delta(1.0, 1.0) == (1.0, -1.0)


def test_morph_entry_edges():
    transform = cubism_native_convert._CanvasTransform(1.0, 0.0, 0.0)  # noqa: SLF001
    build = cubism_native_convert._build_morph_entry  # noqa: SLF001
    assert build([0.0, 0.0], [0.0], [0.0, 0.0], 0.001, transform, "P") is None
    assert build([0.0, 0.0], [0.0, 0.0], [0.0, 0.0005], 0.001, transform, "P") is None
    assert build([0.0, 0.0], [0.0, 0.0], [0.0, 0.001], 0.001, transform, "P") == {
        "parameter": "P", "delta_at_min": [(0.0, -0.0)],
        "delta_at_max": [(0.0, -0.001)],
    }
    assert cubism_native_convert._max_abs([]) == 0.0  # noqa: SLF001
    assert cubism_native_convert._translate_blend_mode(2) == "multiply"  # noqa: SLF001


def test_private_helpers_stay_importable_from_the_facade():
    for name in (
        "DEFAULT_MORPH_EPSILON", "_attach_visibility_keys", "_load_referenced_motion",
        "_attach_morphs", "_attach_drawables", "_attach_cubism_bundle",
        "_collect_single_sidecar", "_emit_opacity_curve", "_sample_at",
    ):
        assert hasattr(cubism_native_convert, name), name


def test_fake_model_satisfies_the_bridge_surface():
    model = cast(CubismModel, _FakeModel())
    assert len(model.vertex_positions()) == 3
