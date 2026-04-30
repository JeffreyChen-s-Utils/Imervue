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
