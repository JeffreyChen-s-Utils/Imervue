"""Tests for the Manga menu — panel cutter commit."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.manga_menu import (
    PANEL_BORDER_DEFAULT,
    PANEL_COLS_DEFAULT,
    PANEL_GUTTER_DEFAULT,
    PANEL_MARGIN_DEFAULT,
    PANEL_ROWS_DEFAULT,
    commit_panel_layout,
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


@pytest.fixture
def default_params():
    return {
        "rows": PANEL_ROWS_DEFAULT,
        "cols": PANEL_COLS_DEFAULT,
        "gutter": PANEL_GUTTER_DEFAULT,
        "border": PANEL_BORDER_DEFAULT,
        "margin": PANEL_MARGIN_DEFAULT,
    }


def test_commit_adds_layer_named_panels(qapp, default_params):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        before = document.layer_count
        ok = commit_panel_layout(ws, default_params)
        assert ok is True
        assert document.layer_count == before + 1
        new_layer = document.layer_at(document.layer_count - 1)
        assert "Panels" in new_layer.name
    finally:
        ws.deleteLater()


def test_commit_paints_visible_borders(qapp, default_params):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        commit_panel_layout(ws, default_params)
        layer = document.layer_at(document.layer_count - 1)
        # The new layer should have at least one opaque pixel (the border).
        assert (layer.image[..., 3] > 0).any()
    finally:
        ws.deleteLater()


def test_commit_returns_false_for_invalid_params(qapp):
    """Negative gutter should be rejected by panel_grid → return False
    so the workspace can show an error rather than crashing."""
    ws = PaintWorkspace()
    try:
        before = ws.canvas().document().layer_count
        ok = commit_panel_layout(ws, {
            "rows": 4, "cols": 1,
            "gutter": -10, "border": 4, "margin": 0,
        })
        assert ok is False
        assert ws.canvas().document().layer_count == before
    finally:
        ws.deleteLater()


def test_commit_returns_false_when_canvas_too_small_for_margins(qapp):
    """Margins larger than the canvas should be rejected gracefully."""
    ws = PaintWorkspace()
    try:
        # Default canvas is small — push margin past it.
        h, w = ws.canvas().document().shape
        before = ws.canvas().document().layer_count
        ok = commit_panel_layout(ws, {
            "rows": 2, "cols": 2,
            "gutter": 4, "border": 2,
            "margin": max(h, w),
        })
        assert ok is False
        assert ws.canvas().document().layer_count == before
    finally:
        ws.deleteLater()


def test_commit_with_no_document_shape_returns_false(qapp, default_params):
    ws = PaintWorkspace()
    try:
        document = ws.canvas().document()
        document._layers.clear()  # noqa: SLF001
        document._composite_cache = None  # noqa: SLF001
        assert commit_panel_layout(ws, default_params) is False
    finally:
        ws.deleteLater()


def test_commit_missing_param_key_returns_false(qapp):
    ws = PaintWorkspace()
    try:
        before = ws.canvas().document().layer_count
        # Missing "border" key → KeyError caught inside commit.
        ok = commit_panel_layout(ws, {
            "rows": 2, "cols": 2, "gutter": 4, "margin": 0,
        })
        assert ok is False
        assert ws.canvas().document().layer_count == before
    finally:
        ws.deleteLater()


def test_workspace_exposes_manga_menu(qapp):
    ws = PaintWorkspace()
    try:
        from Imervue.paint.paint_menu_bar import menu_for
        menu = menu_for(ws, "manga")
        # Should have at least the Panel Cutter action.
        actions = [a.text() for a in menu.actions()]
        assert any("Panel" in a or "分格" in a or "コマ" in a or "컷" in a
                   for a in actions)
    finally:
        ws.deleteLater()


def test_toggle_tone_layer_installs_default_settings(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._manga_menu_bridge   # noqa: SLF001
        bridge.toggle_tone_layer()
        layer = ws.canvas().document().active_layer()
        assert layer.tone is not None
    finally:
        ws.deleteLater()


def test_toggle_tone_layer_clears_existing_tone(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._manga_menu_bridge   # noqa: SLF001
        bridge.toggle_tone_layer()
        bridge.toggle_tone_layer()
        layer = ws.canvas().document().active_layer()
        assert layer.tone is None
    finally:
        ws.deleteLater()


def test_toggle_tone_layer_no_op_without_active():
    """Empty document → no-op rather than crash."""
    from Imervue.paint.document import PaintDocument
    from Imervue.paint.manga_menu import _MangaMenuBridge

    class _Stub:
        def __init__(self):
            self._doc = PaintDocument()

        def canvas(self):
            return self

        def document(self):
            return self._doc

        def update(self):
            pass

    bridge = _MangaMenuBridge.__new__(_MangaMenuBridge)
    bridge._workspace = _Stub()  # noqa: SLF001
    # No active layer; the bridge must short-circuit.
    bridge.toggle_tone_layer()
    assert bridge._workspace.document().active_layer() is None  # noqa: SLF001


def test_stamp_page_numbers_no_project_is_safe(qapp):
    """Without a project mounted on the workspace the verb must be a
    silent no-op — guards against a binding that crashes a brand-new
    workspace before the user opens a multi-page project."""
    ws = PaintWorkspace()
    try:
        bridge = ws._manga_menu_bridge   # noqa: SLF001
        # No _paint_project attribute — verb must short-circuit.
        bridge.stamp_page_numbers()
    finally:
        ws.deleteLater()


def test_stamp_page_numbers_runs_against_attached_project(qapp):
    import numpy as np
    from Imervue.paint.document import PaintDocument
    from Imervue.paint.paint_project import PaintProject, ProjectPage
    ws = PaintWorkspace()
    try:
        proj = PaintProject(name="p")
        for _ in range(2):
            doc = PaintDocument()
            doc.load_image(np.zeros((32, 32, 4), dtype=np.uint8))
            proj.add_page(ProjectPage(document=doc, name="P"))
        ws._paint_project = proj   # noqa: SLF001
        before = [p.document.layer_count for p in proj.pages]
        bridge = ws._manga_menu_bridge   # noqa: SLF001
        bridge.stamp_page_numbers()
        after = [p.document.layer_count for p in proj.pages]
        assert all(a == b + 1 for a, b in zip(after, before, strict=True))
    finally:
        ws.deleteLater()


def test_add_speedlines_inserts_layer_with_content(qapp):
    import numpy as np
    ws = PaintWorkspace()
    try:
        bridge = ws._manga_menu_bridge   # noqa: SLF001
        document = ws.canvas().document()
        before = document.layer_count
        bridge.add_speedlines("radial")
        assert document.layer_count == before + 1
        layer = document.active_layer()
        assert (layer.image[..., 3] > 0).any()
        # Confirm a non-default kind is also valid.
        bridge.add_speedlines("parallel")
        assert document.layer_count == before + 2
        # Sanity guard for unused locals.
        _ = np
    finally:
        ws.deleteLater()


def test_add_flash_inserts_layer_with_content(qapp):
    ws = PaintWorkspace()
    try:
        bridge = ws._manga_menu_bridge   # noqa: SLF001
        document = ws.canvas().document()
        before = document.layer_count
        bridge.add_flash()
        assert document.layer_count == before + 1
        layer = document.active_layer()
        assert (layer.image[..., 3] > 0).any()
        assert layer.name == "Flash"
    finally:
        ws.deleteLater()
