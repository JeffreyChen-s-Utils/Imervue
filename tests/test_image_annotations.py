"""Tests for the non-destructive annotation-layer storage.

Pure-Python — no Qt. Covers:

* dataclass construction + serialisation round-trip
* sidecar I/O (path, load, save, empty-deletes-file)
* loader robustness on malformed JSON / wrong-typed fields
* coordinate-space helpers (normalize / denormalize)
* per-kind point-count validation
"""
from __future__ import annotations

import json

import pytest

from Imervue.image.annotations import (
    DEFAULT_COLOR,
    DEFAULT_STROKE_PX,
    SCHEMA_VERSION,
    SUPPORTED_KINDS,
    Annotation,
    AnnotationLayer,
    denormalize_point,
    has_sidecar,
    load,
    normalize_point,
    save,
    sidecar_path_for,
)


# ---------------------------------------------------------------
# Sidecar path / existence
# ---------------------------------------------------------------


def test_sidecar_path_is_suffixed(tmp_path):
    img = tmp_path / "photo.jpg"
    out = sidecar_path_for(img)
    assert out.name == "photo.jpg.annotations.json"
    assert out.parent == tmp_path


def test_has_sidecar_missing(tmp_path):
    assert has_sidecar(tmp_path / "nope.jpg") is False


def test_has_sidecar_present(tmp_path):
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text("{}", encoding="utf-8")
    assert has_sidecar(img) is True


# ---------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------


def test_save_then_load_round_trips(tmp_path):
    img = tmp_path / "photo.jpg"
    layer = AnnotationLayer(annotations=[
        Annotation(
            kind="arrow",
            points=((0.1, 0.2), (0.8, 0.9)),
            color="#ff0000",
            stroke_px=4.0,
        ),
        Annotation(
            kind="text",
            points=((0.5, 0.5),),
            text="needs cropping",
            color="#00ff00",
        ),
    ])
    save(img, layer)
    reloaded = load(img)
    assert len(reloaded.annotations) == 2
    arrow, text = reloaded.annotations
    assert arrow.kind == "arrow"
    assert arrow.points == ((0.1, 0.2), (0.8, 0.9))
    assert arrow.color == "#ff0000"
    assert text.kind == "text"
    assert text.text == "needs cropping"


def test_save_empty_layer_deletes_sidecar(tmp_path):
    """Removing the last annotation should not leave a stray
    sidecar file polluting the user's folder."""
    img = tmp_path / "photo.jpg"
    layer = AnnotationLayer(annotations=[
        Annotation(kind="rect", points=((0.0, 0.0), (1.0, 1.0))),
    ])
    save(img, layer)
    assert has_sidecar(img)
    save(img, AnnotationLayer())
    assert not has_sidecar(img)


def test_save_empty_layer_when_no_sidecar_is_noop(tmp_path):
    """Empty + no sidecar present → must not raise on the
    nonexistent unlink path."""
    img = tmp_path / "photo.jpg"
    save(img, AnnotationLayer())   # no raise


def test_load_missing_returns_empty_layer(tmp_path):
    layer = load(tmp_path / "nope.jpg")
    assert isinstance(layer, AnnotationLayer)
    assert layer.is_empty()
    assert layer.schema_version == SCHEMA_VERSION


# ---------------------------------------------------------------
# Loader robustness
# ---------------------------------------------------------------


def test_load_malformed_json_returns_empty(tmp_path):
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text("not json at all", encoding="utf-8")
    layer = load(img)
    assert layer.is_empty()


def test_load_non_object_root_returns_empty(tmp_path):
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text("[1, 2, 3]", encoding="utf-8")
    assert load(img).is_empty()


def test_load_drops_unknown_kinds(tmp_path):
    """Forward-compat: a future-schema kind from a newer runtime
    must be ignored, not crash the loader."""
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text(json.dumps({
        "annotations": [
            {"kind": "arrow", "points": [[0.1, 0.2], [0.3, 0.4]]},
            {"kind": "future_shape_v2", "points": [[0.0, 0.0]]},
        ],
    }), encoding="utf-8")
    layer = load(img)
    assert len(layer.annotations) == 1
    assert layer.annotations[0].kind == "arrow"


def test_load_drops_arrows_with_too_few_points(tmp_path):
    """An arrow needs 2 points — a one-point arrow is meaningless
    and would crash the renderer."""
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text(json.dumps({
        "annotations": [
            {"kind": "arrow", "points": [[0.5, 0.5]]},
            {"kind": "arrow", "points": [[0.1, 0.1], [0.9, 0.9]]},
        ],
    }), encoding="utf-8")
    layer = load(img)
    assert len(layer.annotations) == 1


def test_load_drops_text_with_zero_points(tmp_path):
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text(json.dumps({
        "annotations": [
            {"kind": "text", "points": [], "text": "no anchor"},
            {"kind": "text", "points": [[0.5, 0.5]], "text": "ok"},
        ],
    }), encoding="utf-8")
    layer = load(img)
    assert len(layer.annotations) == 1
    assert layer.annotations[0].text == "ok"


def test_load_clamps_points_to_unit_range(tmp_path):
    """A typo or buggy writer could produce coords outside [0,1].
    Clamp rather than reject — the renderer needs valid input."""
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text(json.dumps({
        "annotations": [
            {"kind": "arrow", "points": [[-0.5, 2.0], [1.5, -1.0]]},
        ],
    }), encoding="utf-8")
    layer = load(img)
    assert len(layer.annotations) == 1
    pts = layer.annotations[0].points
    assert pts == ((0.0, 1.0), (1.0, 0.0))


def test_load_clamps_extreme_stroke_px(tmp_path):
    """Stroke width outside the safe range clamps — a 10000-pixel
    stroke would paint the whole image opaque."""
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text(json.dumps({
        "annotations": [
            {"kind": "arrow", "points": [[0.1, 0.1], [0.2, 0.2]],
             "stroke_px": 10000},
            {"kind": "arrow", "points": [[0.3, 0.3], [0.4, 0.4]],
             "stroke_px": -5},
        ],
    }), encoding="utf-8")
    layer = load(img)
    assert layer.annotations[0].stroke_px == 50.0
    assert layer.annotations[1].stroke_px == 0.5


def test_load_uses_defaults_for_missing_optional_fields(tmp_path):
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text(json.dumps({
        "annotations": [
            {"kind": "arrow", "points": [[0.1, 0.1], [0.2, 0.2]]},
        ],
    }), encoding="utf-8")
    layer = load(img)
    ann = layer.annotations[0]
    assert ann.color == DEFAULT_COLOR
    assert ann.stroke_px == DEFAULT_STROKE_PX
    assert ann.text == ""


def test_load_skips_garbage_annotation_entries(tmp_path):
    """A list with mixed valid + invalid entries → keep the valid
    ones, drop the rest."""
    img = tmp_path / "photo.jpg"
    sidecar_path_for(img).write_text(json.dumps({
        "annotations": [
            {"kind": "arrow", "points": [[0.1, 0.1], [0.2, 0.2]]},
            "not a dict",
            None,
            42,
            {"kind": "rect", "points": [[0.0, 0.0], [1.0, 1.0]]},
        ],
    }), encoding="utf-8")
    layer = load(img)
    assert len(layer.annotations) == 2


def test_supported_kinds_constant_matches_renderer_contract():
    """Sanity guard: if a future commit adds a sixth kind, the
    UI / renderer must add support too. Test fails so it's not
    silent."""
    assert SUPPORTED_KINDS == ("arrow", "rect", "circle", "freehand", "text")


# ---------------------------------------------------------------
# Coordinate-space helpers
# ---------------------------------------------------------------


def test_normalize_point_basic():
    assert normalize_point((100, 200), (400, 800)) == pytest.approx((0.25, 0.25))


def test_normalize_point_clamps_out_of_range():
    """Drag past the image edge during annotation → clamp to the
    edge, not extrapolate outside."""
    assert normalize_point((-50, 1000), (400, 800)) == pytest.approx((0.0, 1.0))


def test_normalize_point_zero_size_returns_origin():
    """Defensive — a stale image ref during teardown must not
    divide by zero."""
    assert normalize_point((100, 200), (0, 0)) == (0.0, 0.0)
    assert normalize_point((100, 200), (-1, 800)) == (0.0, 0.0)


def test_denormalize_point_round_trips_with_normalize():
    """norm → denorm → matches the original (modulo float)."""
    original = (123, 456)
    image_size = (1920, 1080)
    norm = normalize_point(original, image_size)
    back = denormalize_point(norm, image_size)
    assert back == pytest.approx(original, abs=0.5)


def test_denormalize_point_clamps_to_image_bounds():
    """Out-of-range normalized coords (somehow) → clamp to image
    extent so the renderer doesn't try to paint past the bitmap."""
    back = denormalize_point((1.5, -0.2), (100, 100))
    assert back == (100.0, 0.0)


# ---------------------------------------------------------------
# Annotation / AnnotationLayer behaviour
# ---------------------------------------------------------------


def test_annotation_to_dict_emits_lists_not_tuples():
    """JSON doesn't have tuples — the serialiser must produce
    plain lists so the file round-trips on a third-party reader."""
    a = Annotation(kind="arrow", points=((0.1, 0.2), (0.3, 0.4)))
    out = a.to_dict()
    assert out["points"] == [[0.1, 0.2], [0.3, 0.4]]


def test_annotation_layer_is_empty_defaults_true():
    assert AnnotationLayer().is_empty() is True


def test_annotation_layer_to_dict_has_schema_version():
    out = AnnotationLayer().to_dict()
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["annotations"] == []
