"""Smoke tests for the assembled Paint workspace."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_workspace_constructs(qapp):
    ws = PaintWorkspace()
    try:
        assert ws.canvas() is not None
        assert ws.state() is ts.load_tool_state()
    finally:
        ws.deleteLater()


def test_workspace_has_eight_dock_widgets(qapp):
    from PySide6.QtWidgets import QDockWidget
    ws = PaintWorkspace()
    try:
        docks = ws.findChildren(QDockWidget)
        # Colour, Brush, Layer, Navigator, Material, History,
        # Swatches, Reference (24d).
        assert len(docks) == 8
    finally:
        ws.deleteLater()


def test_workspace_has_two_toolbars(qapp):
    from PySide6.QtWidgets import QToolBar
    ws = PaintWorkspace()
    try:
        # PaintToolBar (left) + PaintOptionsBar (top) = 2 direct toolbars.
        bars = [b for b in ws.findChildren(QToolBar) if b.parent() is ws]
        assert len(bars) == 2
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Tool state propagation
# ---------------------------------------------------------------------------


def test_workspace_tool_change_updates_canvas_cursor(qapp):
    ws = PaintWorkspace()
    try:
        ws.state().set_tool("hand")
        from PySide6.QtCore import Qt
        assert ws.canvas().cursor().shape() == Qt.CursorShape.OpenHandCursor
    finally:
        ws.deleteLater()


def test_workspace_load_image_forwards_to_canvas(qapp, sample_rgba_array):
    ws = PaintWorkspace()
    try:
        ws.load_image(sample_rgba_array)
        assert ws.canvas().current_image() is not None
        assert ws.canvas().current_image().shape == sample_rgba_array.shape
    finally:
        ws.deleteLater()


def test_workspace_starts_with_paintable_default_canvas(qapp):
    """Regression for "下筆後沒顏色": a fresh PaintWorkspace must come
    up with a non-empty document so the brush has somewhere to paint.
    Without this seed, ``current_image()`` is ``None`` and the tool
    dispatcher silently no-ops on every stroke."""
    ws = PaintWorkspace()
    try:
        img = ws.canvas().current_image()
        assert img is not None
        h, w = img.shape[:2]
        assert h > 0 and w > 0
        # The default fill is opaque white.
        assert tuple(img[0, 0]) == (255, 255, 255, 255)
    finally:
        ws.deleteLater()


def test_workspace_navigator_shows_preview_after_init(qapp):
    """Regression: NavigatorDock.set_preview_image is wired now —
    the user must see the seeded blank canvas in the navigator,
    not the "(no canvas)" placeholder."""
    ws = PaintWorkspace()
    try:
        # __init__ pushed the seeded canvas into the dock synchronously.
        pixmap = ws._navigator_dock._preview.pixmap()  # noqa: SLF001
        assert pixmap is not None
        assert not pixmap.isNull()
        assert ws._navigator_dock._preview.text() == ""  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_navigator_preview_refreshes_after_paint(qapp):
    """After a brush stroke the navigator preview must reflect the new
    pixels. The ``document_changed`` signal triggers a debounced
    QTimer; we fire it directly to avoid waiting on the event loop."""
    from Imervue.paint.canvas import PointerEvent

    ws = PaintWorkspace()
    try:
        ws.state().set_foreground((255, 0, 0))
        evt = PointerEvent(
            phase="press", x=5.0, y=5.0,
            button=1, modifiers=0, pressure=1.0,
        )
        ws._dispatcher(evt)  # noqa: SLF001
        # Trigger the throttle directly.
        ws._refresh_navigator_preview()  # noqa: SLF001
        pixmap = ws._navigator_dock._preview.pixmap()  # noqa: SLF001
        assert pixmap is not None
        assert not pixmap.isNull()
    finally:
        ws.deleteLater()


def test_workspace_navigator_zoom_slider_drives_canvas_zoom(qapp):
    """The Navigator dock's zoom slider must actually change the canvas
    zoom (it used to only log)."""
    ws = PaintWorkspace()
    try:
        ws.show()
        from PySide6.QtTest import QTest
        QTest.qWait(20)
        # Slider value 200 means 2.0x zoom (slider is value/100).
        ws._navigator_dock._zoom_slider.setValue(200)  # noqa: SLF001
        QTest.qWait(20)
        assert ws.canvas().zoom_factor() == pytest.approx(2.0)
    finally:
        ws.deleteLater()


def test_workspace_canvas_zoom_change_syncs_slider(qapp):
    """Programmatic zoom (or wheel) on the canvas must move the
    Navigator slider so the two stay in sync."""
    ws = PaintWorkspace()
    try:
        ws.show()
        from PySide6.QtTest import QTest
        QTest.qWait(20)
        ws.canvas().set_zoom(1.5)
        QTest.qWait(20)
        slider_value = ws._navigator_dock._zoom_slider.value()  # noqa: SLF001
        # Slider stores percentage so 1.5x → 150.
        assert slider_value == 150
    finally:
        ws.deleteLater()


def test_workspace_remains_paintable_after_main_window_none_bind(qapp):
    """Regression for the actual user-reported "下筆沒反應": when the
    host main window switches to the Paint tab without an image bound
    to the viewer, it calls ``paint_workspace.load_image(None)``.
    After that the brush must still paint — i.e. the workspace must
    have a layer to paint into, not an empty document."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    ws = PaintWorkspace()
    try:
        ws.resize(1200, 800)
        ws.show()
        QTest.qWait(50)

        # Simulate exactly what the main window does on tab change with
        # no current image.
        ws.load_image(None)
        assert ws.canvas().current_image() is not None

        ws.state().set_foreground((0, 128, 255))
        canvas = ws.canvas()
        cx = canvas.width() // 2
        cy = canvas.height() // 2
        before = canvas.current_image().copy()
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx, cy))
        QTest.qWait(20)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx, cy))
        QTest.qWait(20)
        assert (before != canvas.current_image()).any()
    finally:
        ws.deleteLater()


def test_workspace_inside_tab_widget_paints_canvas(qapp):
    """Regression: when the workspace is the active widget of a host
    QTabWidget (the real main-window structure), the layout converges
    to a different canvas size *after* the initial fit. Without re-
    fitting on resize, pan / zoom go stale and a click at the widget
    centre maps to image coordinates outside the canvas — every dab
    is off-canvas and the brush silently no-ops, even though the
    layer dock + button still works."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QMainWindow, QTabWidget

    host = QMainWindow()
    host.resize(1400, 900)
    tabs = QTabWidget(host)
    host.setCentralWidget(tabs)

    ws = PaintWorkspace(parent=host)
    tabs.addTab(ws, "Paint")
    tabs.setCurrentWidget(ws)
    host.show()
    QTest.qWait(100)
    try:
        ws.state().set_foreground((255, 0, 0))
        canvas = ws.canvas()
        # Click at widget centre must land somewhere inside the document.
        cx = canvas.width() // 2
        cy = canvas.height() // 2
        img_x, img_y = canvas._screen_to_image(cx, cy)  # noqa: SLF001
        h, w = canvas.current_image().shape[:2]
        assert 0 <= img_x < w, f"image x {img_x} outside [0, {w})"
        assert 0 <= img_y < h, f"image y {img_y} outside [0, {h})"

        before = canvas.current_image().copy()
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx, cy))
        QTest.qWait(20)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx, cy))
        QTest.qWait(20)
        assert (before != canvas.current_image()).any()
    finally:
        host.deleteLater()


def test_workspace_qtest_mouse_click_paints_canvas(qapp):
    """QTest-driven regression: a real Qt mouse press on a shown
    workspace must paint the active layer. This goes through the full
    mousePressEvent → _dispatch → dispatcher → brush → apply_dab path,
    catching wiring breaks the synthetic dispatcher tests miss."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    ws = PaintWorkspace()
    try:
        ws.resize(1200, 800)
        ws.show()
        QTest.qWait(50)
        ws.state().set_foreground((255, 0, 0))

        canvas = ws.canvas()
        before = canvas.current_image().copy()
        cx = canvas.width() // 2
        cy = canvas.height() // 2
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx, cy))
        QTest.qWait(20)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx, cy))
        QTest.qWait(20)

        after = canvas.current_image()
        assert (before != after).any(), "real mouse click must paint the canvas"
        # Canvas has been laid out — fit must have applied (zoom > min).
        from Imervue.paint.canvas import ZOOM_MIN
        assert canvas.zoom_factor() > ZOOM_MIN
    finally:
        ws.deleteLater()


def test_workspace_layer_dock_plus_button_adds_layer(qapp):
    """QTest-driven regression: clicking the LayerDock '+' button must
    add a layer to the underlying document. Goes through Qt's clicked
    signal so any wiring break (e.g. lambda capture, signal disconnect
    via stale Python wrapper) surfaces here."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QToolButton

    ws = PaintWorkspace()
    try:
        ws.show()
        QTest.qWait(50)

        dock = ws._layer_dock  # noqa: SLF001
        before_count = dock._document.layer_count  # noqa: SLF001

        buttons = dock.findChildren(QToolButton)
        # The five buttons are add / remove / up / down / duplicate, in
        # that order. Index 0 is the add ('+') button.
        assert len(buttons) == 5
        buttons[0].click()
        QTest.qWait(20)

        assert dock._document.layer_count == before_count + 1  # noqa: SLF001
        assert dock._list.count() == before_count + 1  # noqa: SLF001
    finally:
        ws.deleteLater()


def test_workspace_brush_press_paints_active_layer(qapp):
    """End-to-end "下筆有顏色" check: brushing on a fresh workspace must
    deposit colour onto the active layer's pixel buffer. Verifies the
    canvas and the document's active layer are the same buffer (no
    copy-on-write surprise) so the LayerDock thumbnail reflects what
    the user just drew."""
    from Imervue.paint.canvas import PointerEvent

    ws = PaintWorkspace()
    try:
        ws.state().set_foreground((255, 0, 0))
        canvas_img = ws.canvas().current_image()
        assert canvas_img is not None
        h, w = canvas_img.shape[:2]
        cx, cy = w // 2, h // 2
        before = tuple(canvas_img[cy, cx])

        evt = PointerEvent(
            phase="press", x=float(cx), y=float(cy),
            button=1, modifiers=0, pressure=1.0,
        )
        assert ws._dispatcher(evt) is True  # noqa: SLF001

        # The dispatcher returns the active layer image, which must be
        # the same buffer the document holds — otherwise the LayerDock
        # would render a stale thumbnail and the "圖層跟畫不一樣"
        # divergence would appear.
        active_layer = ws.canvas().document().active_layer()
        assert active_layer is not None
        assert active_layer.image is canvas_img
        after = tuple(canvas_img[cy, cx])
        assert after != before
        assert after[0] == 255 and after[1] == 0 and after[2] == 0
    finally:
        ws.deleteLater()


def test_workspace_dispatcher_receives_canvas_for_first_press(qapp):
    """End-to-end regression: dispatching a press on a fresh workspace
    must reach the active tool's ``handle`` with a real numpy buffer.
    Before the default-canvas seed, ``image_provider`` returned ``None``
    and ``ToolDispatcher.__call__`` short-circuited to ``False``."""
    import numpy as np

    from Imervue.paint.canvas import PointerEvent

    ws = PaintWorkspace()
    try:
        captured: list = []

        class _CapturingTool:
            def handle(self, evt, canvas):
                captured.append((evt, canvas))
                return False

            def cancel(self):
                pass

        # Swap the real brush handler for a probe so we observe what the
        # dispatcher hands to a tool — without mutating the global tool
        # registry. The active tool remains ``"brush"`` (the default).
        dispatcher = ws._dispatcher  # noqa: SLF001
        dispatcher._handlers["brush"] = _CapturingTool()  # noqa: SLF001

        evt = PointerEvent(
            phase="press", x=5.0, y=5.0,
            button=1, modifiers=0, pressure=1.0,
        )
        dispatcher(evt)

        assert len(captured) == 1
        _, canvas_arr = captured[0]
        assert isinstance(canvas_arr, np.ndarray)
        assert canvas_arr.ndim == 3
        assert canvas_arr.shape[2] == 4
    finally:
        ws.deleteLater()


def test_workspace_load_image_none_resets_to_blank_canvas(qapp, sample_rgba_array):
    """Regression: the host main window calls
    ``paint_workspace.load_image(None)`` whenever the viewer has no
    current image. That used to clear the document outright, which
    wiped the seeded blank canvas from ``__init__`` — every brush
    stroke after that no-opped because ``current_image()`` returned
    ``None``. ``load_image(None)`` must reset to a fresh blank canvas
    so the workspace stays paintable."""
    ws = PaintWorkspace()
    try:
        ws.load_image(sample_rgba_array)
        ws.load_image(None)
        img = ws.canvas().current_image()
        assert img is not None
        # Default blank fill is opaque white.
        assert tuple(img[0, 0]) == (255, 255, 255, 255)
    finally:
        ws.deleteLater()


def test_workspace_load_image_rejects_wrong_shape(qapp, sample_rgb_array):
    ws = PaintWorkspace()
    try:
        with pytest.raises(ValueError):
            ws.load_image(sample_rgb_array)
    finally:
        ws.deleteLater()


# ---------------------------------------------------------------------------
# Translation coverage
# ---------------------------------------------------------------------------


def test_paint_translations_match_across_languages():
    """Every paint_* key must exist in all five built-in languages."""
    from Imervue.multi_language.chinese import chinese_word_dict
    from Imervue.multi_language.english import english_word_dict
    from Imervue.multi_language.japanese import japanese_word_dict
    from Imervue.multi_language.korean import korean_word_dict
    from Imervue.multi_language.traditional_chinese import (
        traditional_chinese_word_dict,
    )

    keys_per_lang = {
        "english": {k for k in english_word_dict if k.startswith("paint_")},
        "tc":      {k for k in traditional_chinese_word_dict if k.startswith("paint_")},
        "cn":      {k for k in chinese_word_dict if k.startswith("paint_")},
        "ja":      {k for k in japanese_word_dict if k.startswith("paint_")},
        "ko":      {k for k in korean_word_dict if k.startswith("paint_")},
    }
    sizes = {len(v) for v in keys_per_lang.values()}
    assert len(sizes) == 1, f"paint key counts differ: {keys_per_lang}"
    # Every language has the same exact set.
    base = keys_per_lang["english"]
    for lang, keys in keys_per_lang.items():
        missing = base - keys
        assert not missing, f"{lang} missing paint keys: {sorted(missing)}"


def test_spanish_plugin_includes_paint_keys():
    import sys
    from pathlib import Path

    plugin_root = Path(__file__).resolve().parent.parent / "plugins"
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    from spanish_translation.spanish import spanish_word_dict
    paint_keys = [k for k in spanish_word_dict if k.startswith("paint_")]
    assert len(paint_keys) >= 90, f"only {len(paint_keys)} spanish paint keys"
