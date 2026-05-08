"""Tests for the brush-kind preview thumbnail renderer."""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_kind_preview import (
    DEFAULT_THUMBNAIL_H,
    DEFAULT_THUMBNAIL_W,
    render_brush_kind_pixmap,
    render_brush_kind_thumbnail,
)


def test_thumbnail_returns_documented_shape():
    arr = render_brush_kind_thumbnail("pen")
    assert arr.shape == (DEFAULT_THUMBNAIL_H, DEFAULT_THUMBNAIL_W, 4)
    assert arr.dtype == np.uint8


def test_thumbnail_paints_visible_stroke():
    """The stroke must light up some non-zero alpha pixels —
    otherwise the icon would be a transparent rectangle."""
    arr = render_brush_kind_thumbnail("pen")
    assert int(arr[..., 3].max()) > 0


def test_thumbnail_color_used_in_stroke():
    """The painted pixels carry the requested ink colour so callers
    can theme thumbnails (dark for light docks, light for dark)."""
    arr = render_brush_kind_thumbnail("pen", color=(200, 0, 0))
    visible = arr[..., 3] > 0
    rgb = arr[visible, :3]
    # Median red channel is high; green / blue medians stay low.
    assert int(np.median(rgb[:, 0])) > 100
    assert int(np.median(rgb[:, 1])) < 80


def test_thumbnail_zero_dimension_raises():
    with pytest.raises(ValueError):
        render_brush_kind_thumbnail("pen", width=0)
    with pytest.raises(ValueError):
        render_brush_kind_thumbnail("pen", height=-3)


@pytest.mark.parametrize("kind", ts.BRUSH_KINDS)
def test_every_kind_renders_a_visible_stroke(kind):
    """Every documented brush kind has to produce a usable preview
    so the combo box never falls back to a blank icon."""
    arr = render_brush_kind_thumbnail(kind)
    assert int(arr[..., 3].max()) > 0


def test_thumbnails_differ_between_kinds():
    """Two distinct kinds must paint distinguishable thumbnails so
    the user can actually tell them apart in the combo box."""
    pen = render_brush_kind_thumbnail("pen")
    pencil = render_brush_kind_thumbnail("pencil")
    assert not np.array_equal(pen, pencil)


def test_pixmap_adapter_returns_qt_pixmap(qapp):
    pix = render_brush_kind_pixmap("pen")
    assert pix is not None
    assert pix.width() == DEFAULT_THUMBNAIL_W
    assert pix.height() == DEFAULT_THUMBNAIL_H
    assert pix.isNull() is False


def test_brush_dock_combo_carries_thumbnails(qapp):
    """End-to-end: BrushDock builds an icon-bearing combo so the
    user sees the preview row inside the dock without further
    wiring."""
    from Imervue.paint.dock_panels import BrushDock
    state = ts.load_tool_state()
    dock = BrushDock(state)
    try:
        assert dock._kind.count() == len(ts.BRUSH_KINDS)  # noqa: SLF001
        # At least one item carries a non-null icon.
        any_icon = any(
            not dock._kind.itemIcon(i).isNull()  # noqa: SLF001
            for i in range(dock._kind.count())  # noqa: SLF001
        )
        assert any_icon
    finally:
        dock.deleteLater()
