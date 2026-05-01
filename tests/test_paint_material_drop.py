"""Tests for the material drag-drop helper."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.document import PaintDocument
from Imervue.paint.material_drop import (
    MATERIAL_MIME_TYPE,
    commit_material_to_document,
    load_material_image,
    paste_material_at,
)


# ---------------------------------------------------------------------------
# load_material_image
# ---------------------------------------------------------------------------


def test_load_material_image_reads_png(tmp_path):
    src = np.zeros((4, 6, 4), dtype=np.uint8)
    src[..., :3] = (200, 100, 50)
    src[..., 3] = 255
    target = tmp_path / "tile.png"
    Image.fromarray(src, mode="RGBA").save(target)
    loaded = load_material_image(target)
    assert loaded.shape == (4, 6, 4)
    assert loaded.dtype == np.uint8
    np.testing.assert_array_equal(loaded, src)


def test_load_material_image_converts_rgb_to_rgba(tmp_path):
    rgb = np.full((4, 4, 3), 200, dtype=np.uint8)
    target = tmp_path / "rgb.png"
    Image.fromarray(rgb, mode="RGB").save(target)
    loaded = load_material_image(target)
    assert loaded.shape == (4, 4, 4)
    assert (loaded[..., 3] == 255).all()


def test_load_material_image_rejects_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_material_image(tmp_path / "missing.png")


# ---------------------------------------------------------------------------
# paste_material_at
# ---------------------------------------------------------------------------


def test_paste_centres_tile_at_drop_point():
    tile = np.full((4, 4, 4), 200, dtype=np.uint8)
    tile[..., 3] = 255
    out = paste_material_at((10, 10), tile, drop_x=5, drop_y=5)
    # Centre of a 4x4 tile dropped at (5,5) lands at canvas (3..6, 3..6).
    assert out[5, 5, 0] == 200
    assert out[0, 0, 3] == 0   # corner stays transparent


def test_paste_clips_overhanging_tile():
    tile = np.full((6, 6, 4), 200, dtype=np.uint8)
    tile[..., 3] = 255
    # Drop near top-left corner — half the tile overhangs.
    out = paste_material_at((10, 10), tile, drop_x=0, drop_y=0)
    # No wrap: bottom-right of canvas is empty.
    assert (out[8:, 8:, 3] == 0).all()
    # Painted cells are within the canvas.
    assert (out[..., 3] > 0).any()


def test_paste_off_canvas_returns_empty_buffer():
    tile = np.full((4, 4, 4), 200, dtype=np.uint8)
    tile[..., 3] = 255
    out = paste_material_at((10, 10), tile, drop_x=-100, drop_y=-100)
    assert out.shape == (10, 10, 4)
    assert (out[..., 3] == 0).all()


def test_paste_rejects_non_rgba():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        paste_material_at((10, 10), bad, drop_x=0, drop_y=0)


def test_paste_rejects_non_uint8():
    bad = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        paste_material_at((10, 10), bad, drop_x=0, drop_y=0)


def test_paste_rejects_non_positive_canvas():
    tile = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError):
        paste_material_at((0, 0), tile, drop_x=0, drop_y=0)


# ---------------------------------------------------------------------------
# commit_material_to_document
# ---------------------------------------------------------------------------


def test_commit_appends_layer_with_tile_pixels():
    doc = PaintDocument()
    doc.load_image(np.zeros((10, 10, 4), dtype=np.uint8))
    tile = np.full((4, 4, 4), 200, dtype=np.uint8)
    tile[..., 3] = 255
    layer = commit_material_to_document(doc, tile, drop_x=5, drop_y=5)
    assert layer is not None
    assert doc.layer_count == 2
    # Centre of the new layer carries the tile colour.
    assert tuple(layer.image[5, 5]) == (200, 200, 200, 255)


def test_commit_returns_none_on_empty_document():
    doc = PaintDocument()  # no shape — no layers
    tile = np.full((4, 4, 4), 200, dtype=np.uint8)
    assert commit_material_to_document(doc, tile, drop_x=0, drop_y=0) is None


def test_commit_uses_provided_layer_name():
    doc = PaintDocument()
    doc.load_image(np.zeros((6, 6, 4), dtype=np.uint8))
    tile = np.full((2, 2, 4), 100, dtype=np.uint8)
    tile[..., 3] = 255
    layer = commit_material_to_document(
        doc, tile, drop_x=3, drop_y=3, name="Bricks",
    )
    assert layer.name == "Bricks"


# ---------------------------------------------------------------------------
# MIME type constant
# ---------------------------------------------------------------------------


def test_material_mime_type_is_namespaced():
    """Reserve a project-scoped MIME identifier so foreign drops are
    not silently misidentified as material drops."""
    assert MATERIAL_MIME_TYPE.startswith("application/x-imervue")
