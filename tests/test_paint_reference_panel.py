"""Tests for the reference image dock data model."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from PIL import Image

from Imervue.paint import reference_panel as rp
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_storage():
    user_setting_dict.pop("paint_reference_panel", None)
    yield
    user_setting_dict.pop("paint_reference_panel", None)


@pytest.fixture
def sample_image_path(tmp_path):
    arr = np.full((40, 40, 3), 200, dtype=np.uint8)
    arr[10:30, 10:30] = (50, 100, 200)
    path = tmp_path / "ref.png"
    Image.fromarray(arr).save(str(path))
    return path


# ---------------------------------------------------------------------------
# ReferenceImage
# ---------------------------------------------------------------------------


def test_reference_image_construction(tmp_path, sample_image_path):
    ref = rp.ReferenceImage(path=str(sample_image_path), scale=2.0)
    assert ref.scale == 2.0
    assert ref.visible is True


def test_reference_image_is_frozen(sample_image_path):
    ref = rp.ReferenceImage(path=str(sample_image_path))
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.scale = 5.0  # type: ignore[misc]


def test_reference_image_rejects_blank_path():
    with pytest.raises(ValueError, match="non-empty"):
        rp.ReferenceImage(path="   ")


def test_reference_image_rejects_zero_scale(sample_image_path):
    with pytest.raises(ValueError, match="scale"):
        rp.ReferenceImage(path=str(sample_image_path), scale=0.0)


def test_reference_image_rejects_oversized_scale(sample_image_path):
    with pytest.raises(ValueError, match="scale"):
        rp.ReferenceImage(path=str(sample_image_path), scale=100.0)


def test_reference_image_rejects_oob_opacity(sample_image_path):
    with pytest.raises(ValueError, match="opacity"):
        rp.ReferenceImage(path=str(sample_image_path), opacity=2.0)


def test_reference_image_round_trip_via_dict(sample_image_path):
    ref = rp.ReferenceImage(
        path=str(sample_image_path), x=10, y=20, scale=1.5,
        rotation_deg=45, opacity=0.5, visible=False,
    )
    rebuilt = rp.ReferenceImage.from_dict(ref.to_dict())
    assert rebuilt == ref


def test_from_dict_clamps_oversized_scale(sample_image_path):
    rebuilt = rp.ReferenceImage.from_dict({
        "path": str(sample_image_path),
        "scale": 50.0,
    })
    assert rebuilt.scale == rp.MAX_SCALE


def test_from_dict_clamps_negative_opacity(sample_image_path):
    rebuilt = rp.ReferenceImage.from_dict({
        "path": str(sample_image_path),
        "opacity": -1.0,
    })
    assert rebuilt.opacity == 0.0


def test_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        rp.ReferenceImage.from_dict("garbage")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ReferencePanel container
# ---------------------------------------------------------------------------


def test_panel_starts_empty():
    panel = rp.ReferencePanel()
    assert panel.references == []


def test_panel_add_appends(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path)))
    assert len(panel.references) == 1


def test_panel_add_at_max_raises(sample_image_path, tmp_path):
    panel = rp.ReferencePanel()
    for _ in range(rp.MAX_REFERENCES):
        panel.add(rp.ReferenceImage(path=str(sample_image_path)))
    with pytest.raises(ValueError, match=str(rp.MAX_REFERENCES)):
        panel.add(rp.ReferenceImage(path=str(sample_image_path)))


def test_panel_remove_at_index(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path), x=1))
    panel.add(rp.ReferenceImage(path=str(sample_image_path), x=2))
    assert panel.remove(0) is True
    assert panel.references[0].x == 2


def test_panel_remove_out_of_range_returns_false():
    panel = rp.ReferencePanel()
    assert panel.remove(0) is False


def test_panel_replace(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path), x=1))
    panel.replace(
        0, rp.ReferenceImage(path=str(sample_image_path), x=99),
    )
    assert panel.references[0].x == 99


def test_panel_replace_out_of_range_returns_false(sample_image_path):
    panel = rp.ReferencePanel()
    assert (
        panel.replace(0, rp.ReferenceImage(path=str(sample_image_path)))
        is False
    )


def test_panel_move_swaps_order(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path), x=1))
    panel.add(rp.ReferenceImage(path=str(sample_image_path), x=2))
    panel.add(rp.ReferenceImage(path=str(sample_image_path), x=3))
    panel.move(0, 2)
    assert [r.x for r in panel.references] == [2, 3, 1]


def test_panel_move_same_position_returns_false(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path)))
    assert panel.move(0, 0) is False


def test_panel_clear_empties_list(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path)))
    panel.clear()
    assert panel.references == []


def test_panel_round_trip_via_dict(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path), scale=1.5))
    rebuilt = rp.ReferencePanel.from_dict(panel.to_dict())
    assert len(rebuilt.references) == 1
    assert rebuilt.references[0].scale == 1.5


def test_panel_from_dict_drops_corrupt_entries(sample_image_path):
    rebuilt = rp.ReferencePanel.from_dict({
        "references": [
            {"path": str(sample_image_path)},
            "garbage",
            {"path": "  "},   # blank → ValueError on construction
            {"path": str(sample_image_path), "scale": 2.0},
        ],
    })
    assert len(rebuilt.references) == 2


# ---------------------------------------------------------------------------
# load_thumbnail
# ---------------------------------------------------------------------------


def test_load_thumbnail_returns_rgba_uint8(sample_image_path):
    arr = rp.load_thumbnail(sample_image_path, max_side=64)
    assert arr.dtype == np.uint8
    assert arr.shape[2] == 4
    assert max(arr.shape[:2]) <= 64


def test_load_thumbnail_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        rp.load_thumbnail(tmp_path / "ghost.png")


def test_load_thumbnail_zero_max_side_raises(sample_image_path):
    with pytest.raises(ValueError, match="max_side"):
        rp.load_thumbnail(sample_image_path, max_side=0)


def test_load_thumbnail_scales_down_large_image(tmp_path):
    big = np.zeros((1024, 1024, 3), dtype=np.uint8)
    path = tmp_path / "big.png"
    Image.fromarray(big).save(str(path))
    arr = rp.load_thumbnail(path, max_side=128)
    assert max(arr.shape[:2]) <= 128


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip(sample_image_path):
    panel = rp.ReferencePanel()
    panel.add(rp.ReferenceImage(path=str(sample_image_path), scale=1.5))
    rp.save_reference_panel(panel)
    reloaded = rp.load_reference_panel()
    assert len(reloaded.references) == 1
    assert reloaded.references[0].scale == 1.5


def test_load_returns_empty_panel_when_nothing_stored():
    assert rp.load_reference_panel().references == []


def test_load_handles_non_dict_storage():
    user_setting_dict["paint_reference_panel"] = ["not", "a", "dict"]
    assert rp.load_reference_panel().references == []
