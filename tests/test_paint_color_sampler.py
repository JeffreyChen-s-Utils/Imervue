"""Tests for the persistent color sampler."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from Imervue.paint.color_sampler import (
    MAX_SAMPLER_POINTS,
    ColorSampler,
    SamplerPoint,
    load_sampler,
    read_all,
    read_at,
    save_sampler,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_color_sampler", None)
    yield
    user_setting_dict.pop("paint_color_sampler", None)


def _gradient_image(h=10, w=10):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            img[y, x] = (x * 25, y * 25, 100, 255)
    return img


# ---------------------------------------------------------------------------
# SamplerPoint
# ---------------------------------------------------------------------------


def test_sampler_point_construction():
    p = SamplerPoint(name="A", x=10, y=20)
    assert p.name == "A"
    assert p.x == 10


def test_sampler_point_is_frozen():
    p = SamplerPoint(name="A", x=0, y=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.x = 5  # type: ignore[misc]


def test_sampler_point_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        SamplerPoint(name="   ", x=0, y=0)


def test_sampler_point_round_trip_via_dict():
    p = SamplerPoint(name="Skin", x=10, y=20, visible=False)
    rebuilt = SamplerPoint.from_dict(p.to_dict())
    assert rebuilt == p


def test_sampler_point_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        SamplerPoint.from_dict("garbage")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ColorSampler
# ---------------------------------------------------------------------------


def test_sampler_starts_empty():
    s = ColorSampler()
    assert s.points == []


def test_sampler_add_appends():
    s = ColorSampler()
    assert s.add(SamplerPoint(name="A", x=0, y=0)) is True
    assert len(s.points) == 1


def test_sampler_add_duplicate_name_returns_false():
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=0, y=0))
    assert s.add(SamplerPoint(name="A", x=5, y=5)) is False
    assert len(s.points) == 1


def test_sampler_add_at_max_returns_false():
    s = ColorSampler()
    for i in range(MAX_SAMPLER_POINTS):
        s.add(SamplerPoint(name=f"P{i}", x=i, y=i))
    assert s.add(SamplerPoint(name="extra", x=0, y=0)) is False


def test_sampler_remove_existing_returns_true():
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=1, y=1))
    s.add(SamplerPoint(name="B", x=2, y=2))
    assert s.remove("A") is True
    assert [p.name for p in s.points] == ["B"]


def test_sampler_remove_unknown_returns_false():
    s = ColorSampler()
    assert s.remove("ghost") is False


def test_sampler_find_returns_point():
    s = ColorSampler()
    target = SamplerPoint(name="A", x=5, y=5)
    s.add(target)
    assert s.find("A") is target
    assert s.find("ghost") is None


def test_sampler_clear_empties_list():
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=0, y=0))
    s.clear()
    assert s.points == []


def test_sampler_round_trip_via_dict():
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=1, y=2))
    s.add(SamplerPoint(name="B", x=3, y=4, visible=False))
    rebuilt = ColorSampler.from_dict(s.to_dict())
    assert [p.name for p in rebuilt.points] == ["A", "B"]
    assert rebuilt.points[1].visible is False


def test_sampler_from_dict_drops_corrupt_points():
    rebuilt = ColorSampler.from_dict({"points": [
        {"name": "Good", "x": 0, "y": 0},
        "garbage",
        {"name": "   ", "x": 0, "y": 0},
        {"name": "Good 2", "x": 1, "y": 1},
    ]})
    names = [p.name for p in rebuilt.points]
    assert names == ["Good", "Good 2"]


# ---------------------------------------------------------------------------
# read_at / read_all
# ---------------------------------------------------------------------------


def test_read_at_returns_pixel_rgba():
    img = _gradient_image()
    rgba = read_at(img, SamplerPoint(name="A", x=4, y=4))
    assert rgba == (100, 100, 100, 255)


def test_read_at_off_canvas_returns_none():
    img = _gradient_image()
    assert read_at(img, SamplerPoint(name="A", x=999, y=999)) is None


def test_read_at_negative_coord_returns_none():
    img = _gradient_image()
    assert read_at(img, SamplerPoint(name="A", x=-1, y=0)) is None


def test_read_at_rejects_non_rgba():
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        read_at(rgb, SamplerPoint(name="A", x=0, y=0))


def test_read_all_returns_per_point_readout():
    img = _gradient_image()
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=2, y=2))
    s.add(SamplerPoint(name="B", x=8, y=8))
    readout = read_all(img, s)
    assert readout["A"] == (50, 50, 100, 255)
    assert readout["B"] == (200, 200, 100, 255)


def test_read_all_invisible_returns_none():
    img = _gradient_image()
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=2, y=2, visible=False))
    readout = read_all(img, s)
    assert readout["A"] is None


def test_read_all_off_canvas_returns_none():
    img = _gradient_image()
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=999, y=999))
    readout = read_all(img, s)
    assert readout["A"] is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip():
    s = ColorSampler()
    s.add(SamplerPoint(name="A", x=10, y=20))
    save_sampler(s)
    rebuilt = load_sampler()
    assert [p.name for p in rebuilt.points] == ["A"]


def test_load_returns_empty_when_nothing_stored():
    assert load_sampler().points == []


def test_load_handles_non_dict_storage():
    user_setting_dict["paint_color_sampler"] = "not a dict"
    assert load_sampler().points == []
