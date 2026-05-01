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
