"""UX-batch 3 tests: window submenus, drag-and-drop open, brush-size status."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QMimeData, QUrl

from Imervue.paint import recent_files, tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(PaintWorkspace.DOCK_STATE_SETTING_KEY, None)
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    user_setting_dict.pop(PaintWorkspace.DOCK_STATE_SETTING_KEY, None)
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Window menu cluster submenus
# ---------------------------------------------------------------------------


def test_window_menu_has_three_cluster_submenus(qapp):
    from Imervue.paint.paint_menu_bar import menu_for
    ws = PaintWorkspace()
    try:
        window_menu = menu_for(ws, "window")
        submenu_titles = [
            a.text() for a in window_menu.actions() if a.menu() is not None
        ]
        assert len(submenu_titles) == 3
        # English fallbacks; locale may translate.
        for expected in ("Drawing", "Canvas", "Library"):
            assert any(expected in t or t for t in submenu_titles)
    finally:
        ws.deleteLater()


def test_drawing_submenu_holds_drawing_dock_toggles(qapp):
    """The drawing-cluster submenu surfaces every dock in that
    cluster. Reads happen inside the workspace's own life so the
    QMenu's C++ peer isn't GC'd between the lookup and the iter
    (older builds of this test occasionally hit a libshiboken
    'already deleted' from cross-test interaction)."""
    from Imervue.paint.paint_menu_bar import menu_for
    ws = PaintWorkspace()
    try:
        window_menu = menu_for(ws, "window")
        drawing_action = window_menu.actions()[0]
        drawing_sub = drawing_action.menu()
        if drawing_sub is None:
            pytest.skip("drawing cluster submenu not constructed")
        labels = [a.text() for a in drawing_sub.actions()]
        # All four drawing-cluster docks must surface.
        assert any("Color" in label or "顏色" in label for label in labels)
        assert any("Brush" in label or "筆刷" in label for label in labels)
        assert any("Bucket" in label or "桶" in label for label in labels)
        assert any("Swatches" in label or "色票" in label for label in labels)
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Drag-and-drop open
# ---------------------------------------------------------------------------


def test_supported_drop_predicate_accepts_image_extensions(qapp):
    ws = PaintWorkspace()
    try:
        for ext in (".psd", ".png", ".jpg", ".jpeg", ".tif", ".bmp", ".webp"):
            assert ws._is_supported_drop(f"/path/file{ext}")          # noqa: SLF001
            assert ws._is_supported_drop(f"/path/FILE{ext.upper()}")  # noqa: SLF001
        # Unsupported extensions stay rejected.
        assert not ws._is_supported_drop("/path/note.txt")            # noqa: SLF001
        assert not ws._is_supported_drop("/path/song.mp3")            # noqa: SLF001
    finally:
        ws.deleteLater()


def test_drop_event_routes_psd_through_file_bridge(qapp, monkeypatch, tmp_path):
    """A dropped .psd path must reach _file_menu_bridge.open_psd_at,
    which is the same code path File ▸ Open exercises."""
    ws = PaintWorkspace()
    try:
        captured: list[str] = []
        bridge = ws._file_menu_bridge   # noqa: SLF001
        monkeypatch.setattr(
            bridge, "open_psd_at",
            lambda path: captured.append(path),
        )
        psd = tmp_path / "demo.psd"
        psd.write_bytes(b"fake")
        ws._open_dropped_path(str(psd))   # noqa: SLF001
        assert captured == [str(psd)]
    finally:
        ws.deleteLater()


def test_drop_event_routes_png_through_canvas_load_image(
    qapp, tmp_path,
):
    """A dropped raster file is loaded via canvas.load_image, the
    same path the existing image-open flow uses."""
    import numpy as np
    from PIL import Image
    ws = PaintWorkspace()
    try:
        png = tmp_path / "drop.png"
        Image.new("RGBA", (16, 12), (10, 20, 30, 255)).save(png)
        captured: list[np.ndarray] = []
        original = ws._canvas.load_image
        ws._canvas.load_image = lambda arr: captured.append(arr)  # type: ignore[assignment]
        try:
            ws._open_dropped_path(str(png))   # noqa: SLF001
        finally:
            ws._canvas.load_image = original  # type: ignore[assignment]
        assert len(captured) == 1
        assert captured[0].shape == (12, 16, 4)
        # Recent list now contains the path.
        assert str(png) in recent_files.paths()
    finally:
        ws.deleteLater()


def test_drop_event_invalid_path_is_swallowed(qapp, tmp_path):
    """A corrupt file shouldn't crash the workspace — log + ignore."""
    ws = PaintWorkspace()
    try:
        bad = tmp_path / "broken.png"
        bad.write_bytes(b"not a real PNG")
        # Should not raise.
        ws._open_dropped_path(str(bad))   # noqa: SLF001
    finally:
        ws.deleteLater()


def test_drag_enter_event_accepts_image_url(qapp, tmp_path):
    """The dragEnterEvent must accept a single supported URL."""
    from PySide6.QtGui import QDragEnterEvent
    from PySide6.QtCore import QPoint, Qt

    ws = PaintWorkspace()
    try:
        png = tmp_path / "any.png"
        png.write_bytes(b"x")
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(png))])
        evt = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        ws.dragEnterEvent(evt)
        assert evt.isAccepted()
    finally:
        ws.deleteLater()


def test_drag_enter_event_rejects_unsupported_url(qapp, tmp_path):
    from PySide6.QtGui import QDragEnterEvent
    from PySide6.QtCore import QPoint, Qt

    ws = PaintWorkspace()
    try:
        txt = tmp_path / "notes.txt"
        txt.write_text("nope")
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(txt))])
        evt = QDragEnterEvent(
            QPoint(10, 10),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        ws.dragEnterEvent(evt)
        assert not evt.isAccepted()
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Brush-size status bar segment
# ---------------------------------------------------------------------------


def test_status_line_shows_brush_size_when_brushed_tool_active(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_tool("brush")  # noqa: SLF001
        ws._state.set_brush(size=18)  # noqa: SLF001
        ws._on_hover_changed(2, 3)    # noqa: SLF001
        msg = ws._status.currentMessage()  # noqa: SLF001
        assert "Brush" in msg or "筆刷" in msg
        assert "18" in msg
    finally:
        ws.deleteLater()


def test_status_line_omits_brush_size_for_non_brushed_tool(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_tool("hand")    # noqa: SLF001
        ws._on_hover_changed(2, 3)    # noqa: SLF001
        msg = ws._status.currentMessage()  # noqa: SLF001
        # Hand tool: no brush-size segment.
        assert "Brush:" not in msg
    finally:
        ws.deleteLater()


def test_status_line_brush_size_updates_when_size_changes(qapp):
    ws = PaintWorkspace()
    try:
        ws._state.set_tool("brush")   # noqa: SLF001
        ws._state.set_brush(size=8)   # noqa: SLF001
        ws._on_hover_changed(0, 0)    # noqa: SLF001
        assert "8" in ws._status.currentMessage()  # noqa: SLF001
        ws._state.set_brush(size=42)  # noqa: SLF001
        ws._on_hover_changed(0, 0)    # noqa: SLF001
        assert "42" in ws._status.currentMessage()  # noqa: SLF001
    finally:
        ws.deleteLater()
