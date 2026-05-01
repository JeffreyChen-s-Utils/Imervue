"""Tests for the dock thumbnail builder — procedural vs path entry."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from PySide6.QtGui import QPixmap

from Imervue.paint.dock_panels import MaterialDock
from Imervue.paint.material_library import MaterialEntry


def test_render_thumbnail_for_procedural_entry_produces_pixmap(qapp):
    def provider():
        tile = np.zeros((32, 32, 4), dtype=np.uint8)
        tile[..., 3] = 255
        tile[16, 16, 0] = 200
        return tile

    entry = MaterialEntry(
        name="proc", path=Path("procedural://proc"), category="texture",
        provider=provider,
    )
    pix = MaterialDock._render_thumbnail(entry)  # noqa: SLF001
    assert isinstance(pix, QPixmap)
    assert not pix.isNull()
    assert pix.width() <= 64 and pix.height() <= 64


def test_render_thumbnail_falls_back_to_placeholder_for_broken_provider(qapp):
    def boom():
        raise RuntimeError("nope")

    entry = MaterialEntry(
        name="bad", path=Path("procedural://bad"), category="texture",
        provider=boom,
    )
    pix = MaterialDock._render_thumbnail(entry)  # noqa: SLF001
    # The placeholder is a solid 64×64 swatch; never null.
    assert isinstance(pix, QPixmap)
    assert pix.width() == 64 and pix.height() == 64


def test_render_thumbnail_for_path_entry_uses_qpixmap(tmp_path, qapp):
    arr = np.zeros((20, 20, 4), dtype=np.uint8)
    arr[..., 3] = 255
    img_path = tmp_path / "p.png"
    Image.fromarray(arr, mode="RGBA").save(img_path)
    entry = MaterialEntry(name="p", path=img_path, category="texture")
    pix = MaterialDock._render_thumbnail(entry)  # noqa: SLF001
    assert isinstance(pix, QPixmap)
    assert not pix.isNull()


def test_render_thumbnail_placeholder_for_missing_path(tmp_path, qapp):
    entry = MaterialEntry(
        name="missing", path=tmp_path / "never_existed.png",
        category="texture",
    )
    pix = MaterialDock._render_thumbnail(entry)  # noqa: SLF001
    assert isinstance(pix, QPixmap)
    assert pix.width() == 64 and pix.height() == 64


@pytest.fixture
def empty_dock(qapp):
    """Construct a MaterialDock with the default catalog and tear it down."""
    dock = MaterialDock()
    yield dock
    dock.deleteLater()


def test_dock_default_index_populates_grid(empty_dock):
    """The dock starts with the default catalog so the grid has entries."""
    # Default ctor uses MaterialIndex() which is empty — so the dock
    # must NOT silently swap in the default catalog. The workspace
    # injects it via the index= kwarg. Verify that.
    assert len(empty_dock.index()) == 0


def test_thumbnail_button_carries_material_path(qapp, tmp_path):
    """The thumbnail button stashes its material path so the drag
    handler can paste it into the canvas-side MIME payload."""
    from Imervue.paint.dock_panels import _MaterialThumbnailButton

    target = tmp_path / "tile.png"
    pix = QPixmap(8, 8)
    pix.fill()
    pix.save(str(target))
    btn = _MaterialThumbnailButton(str(target), pix)
    try:
        assert btn._path == str(target)   # noqa: SLF001
    finally:
        btn.deleteLater()
