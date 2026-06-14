"""Tests for the multi-view secondary window + workspace plumbing."""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QPixmap

from Imervue.paint import tool_state as ts
from Imervue.paint.multi_view import (
    VIEW_DEFAULT_SCALE,
    VIEW_MAX_SCALE,
    VIEW_MIN_SCALE,
    SecondaryView,
    composite_to_pixmap,
)
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


def _composite(h: int = 16, w: int = 16, c=(200, 100, 50)) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = c[0]
    arr[..., 1] = c[1]
    arr[..., 2] = c[2]
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# composite_to_pixmap
# ---------------------------------------------------------------------------


def test_composite_to_pixmap_returns_qpixmap(qapp):
    pix = composite_to_pixmap(_composite())
    assert isinstance(pix, QPixmap)
    assert not pix.isNull()


def test_composite_to_pixmap_handles_none_input(qapp):
    assert composite_to_pixmap(None) is None


def test_composite_to_pixmap_rejects_non_rgba(qapp):
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    assert composite_to_pixmap(bad) is None


def test_composite_to_pixmap_rejects_non_uint8(qapp):
    bad = np.zeros((4, 4, 4), dtype=np.float32)
    assert composite_to_pixmap(bad) is None


# ---------------------------------------------------------------------------
# SecondaryView basics
# ---------------------------------------------------------------------------


@pytest.fixture
def view(qapp):
    v = SecondaryView()
    yield v
    v.deleteLater()


def test_view_starts_at_default_scale(view):
    assert view.scale_factor() == VIEW_DEFAULT_SCALE


def test_view_set_scale_clamps_to_min(view):
    view.set_scale(0.0001)
    assert view.scale_factor() == VIEW_MIN_SCALE


def test_view_set_scale_clamps_to_max(view):
    view.set_scale(99999.0)
    assert view.scale_factor() == VIEW_MAX_SCALE


def test_view_zoom_in_increases_scale(view):
    before = view.scale_factor()
    view.zoom_in()
    assert view.scale_factor() > before


def test_view_zoom_out_decreases_scale(view):
    view.set_scale(2.0)
    view.zoom_out()
    assert view.scale_factor() < 2.0


def test_view_reset_zoom_returns_to_default(view):
    view.set_scale(3.5)
    view.reset_zoom()
    assert view.scale_factor() == VIEW_DEFAULT_SCALE


def test_view_set_scale_idempotent_short_circuits(view):
    view.set_scale(2.0)
    label_before = view._zoom_label.text()  # noqa: SLF001
    view.set_scale(2.0)
    assert view._zoom_label.text() == label_before  # noqa: SLF001


def test_view_set_composite_with_none_clears(view):
    view.set_composite(composite_to_pixmap(_composite()))
    view.set_composite(None)
    # The label resets when there's no pixmap.
    assert view._image_label.pixmap().isNull()  # noqa: SLF001


def test_view_close_emits_signal(view):
    fired: list[bool] = []
    view.closed.connect(lambda: fired.append(True))
    view.close()
    assert fired == [True]


# ---------------------------------------------------------------------------
# Workspace integration
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_open_secondary_view_grows_count(workspace):
    assert workspace.secondary_view_count() == 0
    workspace.open_secondary_view()
    assert workspace.secondary_view_count() == 1


def test_open_secondary_view_can_have_multiple(workspace):
    workspace.open_secondary_view()
    workspace.open_secondary_view()
    assert workspace.secondary_view_count() == 2


def test_secondary_view_close_drops_from_workspace(workspace):
    view = workspace.open_secondary_view()
    view.close()
    assert workspace.secondary_view_count() == 0


def test_workspace_pushes_composite_to_secondary_views(workspace):
    """A document refresh should propagate to every open view."""
    workspace.open_secondary_view()
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (10, 20, 30)
    workspace._refresh_navigator_preview()  # noqa: SLF001
    view = workspace._secondary_views[0]  # noqa: SLF001
    pixmap = view._composite_pixmap  # noqa: SLF001
    assert pixmap is not None
    assert not pixmap.isNull()


def test_secondary_view_seeded_with_current_composite_on_open(workspace):
    """Opening a view mid-session should immediately show the
    current composite — not wait for the next document change."""
    layer = workspace.canvas().document().active_layer()
    layer.image[..., :3] = (50, 100, 150)
    view = workspace.open_secondary_view()
    assert view._composite_pixmap is not None  # noqa: SLF001


def test_window_menu_has_new_view_action(workspace):
    from Imervue.paint.paint_menu_bar import menu_for
    window_menu = menu_for(workspace, "window")
    labels = [a.text() for a in window_menu.actions() if not a.isSeparator()]
    # Translation may differ — just look for the New View entry by
    # its English fallback.
    assert any("New View" in label or "新" in label or "新規" in label
               or "보조" in label or "뷰" in label
               for label in labels)


# ---------------------------------------------------------------------------
# Mirror preview (28d)
# ---------------------------------------------------------------------------


def test_secondary_view_default_is_not_mirrored(qapp):
    view = SecondaryView()
    try:
        assert view.is_mirror_horizontal() is False
    finally:
        view.deleteLater()


def test_secondary_view_constructor_accepts_mirror_flag(qapp):
    view = SecondaryView(mirror_horizontal=True)
    try:
        assert view.is_mirror_horizontal() is True
    finally:
        view.deleteLater()


def test_set_mirror_horizontal_round_trips(qapp):
    view = SecondaryView()
    try:
        view.set_mirror_horizontal(True)
        assert view.is_mirror_horizontal() is True
        view.set_mirror_horizontal(False)
        assert view.is_mirror_horizontal() is False
    finally:
        view.deleteLater()


def test_open_mirror_preview_returns_mirrored_view(workspace):
    view = workspace.open_mirror_preview()
    assert view.is_mirror_horizontal() is True


def test_open_secondary_view_default_is_unmirrored(workspace):
    view = workspace.open_secondary_view()
    assert view.is_mirror_horizontal() is False


def test_mirror_preview_window_title_is_distinct(workspace):
    plain_view = workspace.open_secondary_view()
    mirror_view = workspace.open_mirror_preview()
    assert plain_view.windowTitle() != mirror_view.windowTitle()


def test_mirror_preview_renders_horizontally_flipped(workspace):
    """A pixel painted on the right half of the source must appear
    on the left half of the rendered (flipped) preview pixmap."""
    layer = workspace.canvas().document().active_layer()
    h, w = layer.image.shape[:2]
    layer.image[..., 3] = 255
    layer.image[..., :3] = 0
    layer.image[:, w - 1, 0] = 255   # red stripe on rightmost column
    workspace.canvas().document().invalidate_composite()
    view = workspace.open_mirror_preview()
    pixmap = view._image_label.pixmap()  # noqa: SLF001
    assert pixmap is not None
    img = pixmap.toImage()
    left_color = img.pixelColor(0, img.height() // 2)
    right_color = img.pixelColor(img.width() - 1, img.height() // 2)
    # Mirrored: the right-side stripe shows up on the left of the preview.
    assert left_color.red() > right_color.red()
    plain_view = workspace.open_secondary_view()
    plain_pix = plain_view._image_label.pixmap()  # noqa: SLF001
    plain_img = plain_pix.toImage()
    plain_left = plain_img.pixelColor(0, plain_img.height() // 2)
    plain_right = plain_img.pixelColor(plain_img.width() - 1, plain_img.height() // 2)
    # Unmirrored: the stripe stays on the right of the preview.
    assert plain_right.red() > plain_left.red()
    # h variable used only for clarity above.
    _ = h


def test_window_menu_has_mirror_preview_action(workspace):
    from Imervue.paint.paint_menu_bar import menu_for
    window_menu = menu_for(workspace, "window")
    labels = [a.text() for a in window_menu.actions() if not a.isSeparator()]
    assert any(
        "Mirror" in label or "鏡" in label or "ミラー" in label
        for label in labels
    )


# ---------------------------------------------------------------------------
# Seamless tile preview (28f)
# ---------------------------------------------------------------------------


def test_secondary_view_default_is_not_tile_preview(qapp):
    view = SecondaryView()
    try:
        assert view.is_tile_preview() is False
    finally:
        view.deleteLater()


def test_secondary_view_constructor_accepts_tile_flag(qapp):
    view = SecondaryView(tile_preview=True)
    try:
        assert view.is_tile_preview() is True
    finally:
        view.deleteLater()


def test_set_tile_preview_round_trips(qapp):
    view = SecondaryView()
    try:
        view.set_tile_preview(True)
        assert view.is_tile_preview() is True
        view.set_tile_preview(False)
        assert view.is_tile_preview() is False
    finally:
        view.deleteLater()


def test_open_tile_preview_returns_tiled_view(workspace):
    view = workspace.open_tile_preview()
    assert view.is_tile_preview() is True


def test_tile_preview_window_title_is_distinct(workspace):
    plain = workspace.open_secondary_view()
    tile = workspace.open_tile_preview()
    assert plain.windowTitle() != tile.windowTitle()


def test_tile_preview_renders_3x3_grid(workspace):
    """The tile preview's pixmap is 3× the source size on each axis
    so the artist sees the wrap on every side."""
    layer = workspace.canvas().document().active_layer()
    h, w = layer.image.shape[:2]
    layer.image[..., :] = (0, 0, 0, 255)
    workspace.canvas().document().invalidate_composite()
    view = workspace.open_tile_preview()
    pixmap = view._image_label.pixmap()  # noqa: SLF001
    assert pixmap is not None
    # 3× tile factor → at least 3× either dimension (scale=1.0).
    assert pixmap.width() >= w * 3
    assert pixmap.height() >= h * 3


def test_tile_pixmap_helper_repeats_source(qapp):
    from Imervue.paint.multi_view import _tile_pixmap

    src = QPixmap(8, 8)
    src.fill()
    out = _tile_pixmap(src, 3)
    assert out.width() == 24
    assert out.height() == 24


def test_tile_pixmap_helper_rejects_zero_repeat(qapp):
    from Imervue.paint.multi_view import _tile_pixmap

    src = QPixmap(4, 4)
    src.fill()
    with pytest.raises(ValueError):
        _tile_pixmap(src, 0)


def test_window_menu_has_tile_preview_action(workspace):
    from Imervue.paint.paint_menu_bar import menu_for
    window_menu = menu_for(workspace, "window")
    labels = [a.text() for a in window_menu.actions() if not a.isSeparator()]
    assert any(
        "Tile" in label or "拼" in label or "タイル" in label
        for label in labels
    )
