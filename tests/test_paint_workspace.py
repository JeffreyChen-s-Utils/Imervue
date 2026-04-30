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


def test_workspace_has_five_dock_widgets(qapp):
    from PySide6.QtWidgets import QDockWidget
    ws = PaintWorkspace()
    try:
        docks = ws.findChildren(QDockWidget)
        assert len(docks) == 5
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


def test_workspace_load_image_none_clears_canvas(qapp, sample_rgba_array):
    ws = PaintWorkspace()
    try:
        ws.load_image(sample_rgba_array)
        ws.load_image(None)
        assert ws.canvas().current_image() is None
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
