"""Tests for the save-region-as-material helper."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.material_library import MaterialIndex
from Imervue.paint.save_region_as_material import (
    save_region_as_material,
    selection_bounds,
)


# ---------------------------------------------------------------------------
# selection_bounds
# ---------------------------------------------------------------------------


def test_selection_bounds_none_returns_none():
    assert selection_bounds(None) is None


def test_selection_bounds_empty_mask_returns_none():
    mask = np.zeros((10, 10), dtype=np.bool_)
    assert selection_bounds(mask) is None


def test_selection_bounds_rejects_non_bool():
    mask = np.zeros((4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        selection_bounds(mask)


def test_selection_bounds_returns_inclusive_rect():
    mask = np.zeros((10, 10), dtype=np.bool_)
    mask[2:5, 3:8] = True
    rect = selection_bounds(mask)
    assert rect == (3, 2, 5, 3)


def test_selection_bounds_handles_single_pixel():
    mask = np.zeros((4, 4), dtype=np.bool_)
    mask[2, 1] = True
    assert selection_bounds(mask) == (1, 2, 1, 1)


# ---------------------------------------------------------------------------
# save_region_as_material — input validation
# ---------------------------------------------------------------------------


@pytest.fixture
def canvas() -> np.ndarray:
    arr = np.zeros((20, 20, 4), dtype=np.uint8)
    arr[..., 3] = 255
    arr[5:10, 5:10, 0] = 200   # red square
    return arr


def test_rejects_non_rgba_canvas(tmp_path):
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        save_region_as_material(
            bad, (0, 0, 4, 4),
            library_root=tmp_path, name="x",
        )


def test_rejects_non_uint8_canvas(tmp_path):
    bad = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        save_region_as_material(
            bad, (0, 0, 4, 4),
            library_root=tmp_path, name="x",
        )


def test_rejects_zero_size_rect(canvas, tmp_path):
    with pytest.raises(ValueError, match="rect dimensions"):
        save_region_as_material(
            canvas, (0, 0, 0, 0),
            library_root=tmp_path, name="x",
        )


def test_rejects_rect_outside_canvas(canvas, tmp_path):
    with pytest.raises(ValueError, match="outside canvas"):
        save_region_as_material(
            canvas, (15, 15, 10, 10),
            library_root=tmp_path, name="x",
        )


def test_rejects_blank_name(canvas, tmp_path):
    with pytest.raises(ValueError, match="name"):
        save_region_as_material(
            canvas, (0, 0, 4, 4),
            library_root=tmp_path, name="   ",
        )


def test_rejects_unknown_category(canvas, tmp_path):
    with pytest.raises(ValueError, match="category"):
        save_region_as_material(
            canvas, (0, 0, 4, 4),
            library_root=tmp_path, name="x",
            category="not-a-category",
        )


def test_rejects_name_with_only_unsafe_chars(canvas, tmp_path):
    with pytest.raises(ValueError, match="filename"):
        save_region_as_material(
            canvas, (0, 0, 4, 4),
            library_root=tmp_path, name="///***",
        )


# ---------------------------------------------------------------------------
# Output side
# ---------------------------------------------------------------------------


def test_save_writes_png_with_cropped_pixels(canvas, tmp_path):
    entry = save_region_as_material(
        canvas, (5, 5, 5, 5),
        library_root=tmp_path, name="redbox",
        category="texture",
    )
    assert entry.path.exists()
    assert entry.category == "texture"
    assert entry.name == "redbox"
    saved = np.asarray(Image.open(entry.path).convert("RGBA"))
    assert saved.shape == (5, 5, 4)
    # The cropped region matches the source pixels.
    np.testing.assert_array_equal(saved, canvas[5:10, 5:10])


def test_save_creates_category_subdirectory(canvas, tmp_path):
    entry = save_region_as_material(
        canvas, (0, 0, 4, 4),
        library_root=tmp_path, name="t",
        category="tone",
    )
    assert entry.path.parent.name == "tone"
    assert entry.path.parent.is_dir()


def test_save_strips_unsafe_filename_chars(canvas, tmp_path):
    entry = save_region_as_material(
        canvas, (0, 0, 4, 4),
        library_root=tmp_path, name="my/material:1",
    )
    # Slash and colon stripped — the resulting stem is filesystem-safe.
    assert "/" not in entry.name
    assert ":" not in entry.name
    assert entry.path.exists()


def test_saved_material_is_picked_up_by_index_rescan(canvas, tmp_path):
    save_region_as_material(
        canvas, (0, 0, 4, 4),
        library_root=tmp_path, name="rescan_me",
        category="pattern",
    )
    index = MaterialIndex.from_directory(tmp_path)
    names = [entry.name for entry in index.entries]
    assert "rescan_me" in names
    pattern_entries = [
        entry for entry in index.entries if entry.category == "pattern"
    ]
    assert len(pattern_entries) >= 1
