"""Tests for the workspace's material → canvas drop pipeline."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.paint import tool_state as ts
from Imervue.paint.material_library import MaterialEntry, default_material_index
from Imervue.paint.material_procedural import dot_tone
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Workspace seeding
# ---------------------------------------------------------------------------


def test_workspace_seeds_dock_with_default_index(qapp):
    ws = PaintWorkspace()
    try:
        index = ws._material_dock.index()  # noqa: SLF001
        # Default catalog is non-empty, so the dock starts populated.
        assert len(index) > 0
        # Every entry from the default catalog is procedural — none of
        # them point at a real on-disk file the user might be missing.
        assert all(e.is_procedural() for e in index.entries)
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Tile drop — adds a layer with the tiled material
# ---------------------------------------------------------------------------


def test_tone_drop_adds_new_layer_filled_with_tile(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        before_count = document.layer_count
        # Pick a procedural tone entry from the default catalog.
        tone_entry = next(
            e for e in default_material_index().entries
            if e.category == "tone"
        )
        ws._on_material_chosen(str(tone_entry.path))  # noqa: SLF001
        after_count = document.layer_count
        assert after_count == before_count + 1
        new_layer = document.layer_at(document.layer_count - 1)
        # New layer name carries the category prefix so the artist
        # can tell what dropped at a glance in the layer dock.
        assert "Tone" in new_layer.name
        # Layer must contain at least one non-transparent pixel —
        # the tile actually got rasterised.
        assert (new_layer.image[..., 3] > 0).any()
    finally:
        ws.deleteLater()


def test_texture_drop_carries_category_in_layer_name(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        texture_entry = next(
            e for e in default_material_index().entries
            if e.category == "texture"
        )
        ws._on_material_chosen(str(texture_entry.path))  # noqa: SLF001
        assert "Texture" in document.layer_at(document.layer_count - 1).name
    finally:
        ws.deleteLater()


def test_pattern_drop_creates_layer(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        before = document.layer_count
        pattern_entry = next(
            e for e in default_material_index().entries
            if e.category == "pattern"
        )
        ws._on_material_chosen(str(pattern_entry.path))  # noqa: SLF001
        assert document.layer_count == before + 1
    finally:
        ws.deleteLater()


def test_drop_respects_active_selection(qapp):
    """If a selection is active, the tile-fill must be confined to
    the selected region — otherwise the user can't drop a tone "into"
    a region they've already lassoed."""
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        h, w = document.shape
        # Build a small rectangular selection in the top-left quadrant.
        mask = np.zeros((h, w), dtype=np.bool_)
        mask[: h // 4, : w // 4] = True
        ws.canvas().set_selection(mask)
        tone_entry = next(
            e for e in default_material_index().entries
            if e.category == "tone"
        )
        ws._on_material_chosen(str(tone_entry.path))  # noqa: SLF001
        layer = document.layer_at(document.layer_count - 1)
        # Pixels outside the selection must be fully transparent.
        outside = layer.image.copy()
        outside[mask] = 0
        assert outside[..., 3].max() == 0
    finally:
        ws.deleteLater()


def test_drop_with_no_document_shape_is_noop(qapp):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        # Nuke the document so shape is None.
        document._layers.clear()  # noqa: SLF001
        document._composite_cache = None  # noqa: SLF001
        before = document.layer_count
        tone_entry = next(
            e for e in default_material_index().entries
            if e.category == "tone"
        )
        ws._on_material_chosen(str(tone_entry.path))  # noqa: SLF001
        # No crash, no layer added.
        assert document.layer_count == before
    finally:
        ws.deleteLater()


def test_brush_tip_drop_does_not_crash(qapp):
    """brush_tip is wired in a later phase — the workspace must
    silently skip the entry instead of raising."""
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        before = document.layer_count
        # Build a synthetic brush_tip entry and pretend it came from
        # the dock. (No brush_tip entries in the default catalog.)
        entry = MaterialEntry(
            name="dummy_tip", path=Path("procedural://dummy_tip"),
            category="brush_tip",
            provider=lambda: dot_tone(size=16, cell=4, coverage=0.5),
        )
        ws._material_dock.index().entries.append(entry)  # noqa: SLF001
        ws._on_material_chosen(str(entry.path))  # noqa: SLF001
        assert document.layer_count == before
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# _load_material_tile — provider failure + path failure handling
# ---------------------------------------------------------------------------


def test_load_material_tile_returns_none_for_broken_provider(qapp):
    def boom():
        raise RuntimeError("simulated provider failure")

    entry = MaterialEntry(
        name="bad", path=Path("procedural://bad"), category="texture",
        provider=boom,
    )
    assert PaintWorkspace._load_material_tile(entry) is None


def test_load_material_tile_returns_none_for_missing_path(tmp_path):
    entry = MaterialEntry(
        name="missing", path=tmp_path / "nope.png", category="texture",
    )
    assert PaintWorkspace._load_material_tile(entry) is None


def test_load_material_tile_returns_none_for_wrong_dtype(qapp):
    entry = MaterialEntry(
        name="float", path=Path("procedural://float"), category="texture",
        provider=lambda: np.zeros((4, 4, 4), dtype=np.float32),
    )
    assert PaintWorkspace._load_material_tile(entry) is None


def test_load_material_tile_loads_real_png(tmp_path):
    """A path-backed entry decodes via PIL into HxWx4 uint8."""
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    arr[..., 3] = 255
    arr[4, 4, 0] = 200
    img_path = tmp_path / "t.png"
    Image.fromarray(arr, mode="RGBA").save(img_path)
    entry = MaterialEntry(name="t", path=img_path, category="texture")
    out = PaintWorkspace._load_material_tile(entry)
    assert out is not None
    assert out.shape == (8, 8, 4)
    assert out.dtype == np.uint8
