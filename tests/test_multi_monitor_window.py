"""Tests for the multi-monitor mirror window.

``_PreviewPanel`` is a plain ``QLabel`` and the controller logic is exercised
with light fakes, so no ``QOpenGLWidget`` is constructed and the headless-CI
skip marker is not required.
"""
from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QKeyEvent

from Imervue.gui import multi_monitor_window as mod
from Imervue.gui.multi_monitor_window import (
    MultiMonitorController,
    MultiMonitorWindow,
    _PreviewPanel,
    array_to_qimage,
    choose_mirror_screen_index,
    next_screen_index,
)


class TestNextScreenIndex:
    def test_forward_wraps(self):
        assert next_screen_index(0, 3, forward=True) == 1
        assert next_screen_index(2, 3, forward=True) == 0

    def test_backward_wraps(self):
        assert next_screen_index(0, 3, forward=False) == 2
        assert next_screen_index(1, 3, forward=False) == 0

    def test_empty_screen_list_is_safe(self):
        assert next_screen_index(0, 0, forward=True) == 0


class TestChooseMirrorScreenIndex:
    def test_prefers_remembered_non_primary_screen(self):
        names = ["DELL", "HP", "LG"]
        # Primary is index 0; remembered "LG" should win over first-other "HP".
        assert choose_mirror_screen_index(names, 0, "LG") == 2

    def test_falls_back_to_first_non_primary(self):
        names = ["A", "B", "C"]
        assert choose_mirror_screen_index(names, 1, None) == 0

    def test_ignores_preferred_when_it_is_the_primary(self):
        names = ["A", "B"]
        # Preferred names the primary screen → skip it, use the other one.
        assert choose_mirror_screen_index(names, 0, "A") == 1

    def test_ignores_preferred_when_absent(self):
        names = ["A", "B"]
        assert choose_mirror_screen_index(names, 0, "GONE") == 1

    def test_single_screen_returns_primary(self):
        assert choose_mirror_screen_index(["only"], 0, None) == 0
        assert choose_mirror_screen_index(["only"], 0, "only") == 0


class TestArrayToQImage:
    def test_rgba_array(self, qapp):
        img = array_to_qimage(np.zeros((4, 5, 4), dtype=np.uint8))
        assert (img.width(), img.height()) == (5, 4)
        assert img.format() == QImage.Format.Format_RGBA8888

    def test_rgb_array(self, qapp):
        img = array_to_qimage(np.zeros((3, 6, 3), dtype=np.uint8))
        assert (img.width(), img.height()) == (6, 3)
        assert img.format() == QImage.Format.Format_RGB888

    def test_detaches_from_source_buffer(self, qapp):
        arr = np.zeros((2, 2, 4), dtype=np.uint8)
        img = array_to_qimage(arr)
        arr[:] = 255  # mutate source after conversion
        # ``.copy()`` means the QImage owns its pixels — unaffected.
        assert img.pixelColor(0, 0).red() == 0

    @pytest.mark.parametrize(
        "shape",
        [(2, 2), (2, 2, 1), (2, 2, 2)],
    )
    def test_invalid_channel_count_raises(self, qapp, shape):
        with pytest.raises(ValueError):
            array_to_qimage(np.zeros(shape, dtype=np.uint8))


class TestPreviewPanel:
    def test_set_array_produces_pixmap(self, qapp):
        panel = _PreviewPanel()
        panel.resize(100, 100)
        panel.set_array(np.zeros((10, 10, 3), dtype=np.uint8))
        assert not panel.pixmap().isNull()

    def test_set_array_none_shows_placeholder_text(self, qapp):
        panel = _PreviewPanel()
        panel.set_array(None)
        assert panel.text()  # localised "No image"


class _FakeViewer:
    def __init__(self):
        self.on_deep_zoom_displayed = None
        self.deep_zoom = None


class _FakeMainWindow:
    def __init__(self):
        self.viewer = _FakeViewer()


class _FakeWindow:
    def __init__(self):
        self.arrays: list = []
        self.images: list = []

    def set_array(self, arr):
        self.arrays.append(arr)

    def set_image(self, path):
        self.images.append(path)


class _FakeDeepZoom:
    def __init__(self, base):
        self.levels = [base]


class TestController:
    def test_deep_zoom_array_is_mirrored_and_forwarded(self):
        ctrl = MultiMonitorController(_FakeMainWindow())
        forwarded: list = []
        ctrl._prev_on_displayed = forwarded.append
        ctrl._window = _FakeWindow()

        arr = np.zeros((2, 2, 3), dtype=np.uint8)
        ctrl._on_deep_zoom_array(arr)

        assert forwarded == [arr]              # chained to prior hook
        assert ctrl._window.arrays == [arr]    # and shown on the mirror

    def test_deep_zoom_array_tolerates_no_prior_hook(self):
        ctrl = MultiMonitorController(_FakeMainWindow())
        ctrl._prev_on_displayed = None
        ctrl._window = _FakeWindow()
        ctrl._on_deep_zoom_array(np.zeros((2, 2, 4), dtype=np.uint8))
        assert len(ctrl._window.arrays) == 1

    def test_mirror_current_pushes_edited_base_level(self):
        mw = _FakeMainWindow()
        base = np.zeros((2, 2, 3), dtype=np.uint8)
        mw.viewer.deep_zoom = _FakeDeepZoom(base)
        ctrl = MultiMonitorController(mw)
        ctrl._window = _FakeWindow()

        ctrl._mirror_current()
        assert ctrl._window.arrays == [base]

    def test_mirror_current_without_image_shows_placeholder(self):
        ctrl = MultiMonitorController(_FakeMainWindow())
        ctrl._window = _FakeWindow()
        ctrl._mirror_current()
        assert ctrl._window.images == [None]


def test_preview_panel_shows_a_tagged_photo_upright(qapp, tmp_path):
    from _decode_samples import tagged_portrait
    panel = _PreviewPanel()
    try:
        panel.set_image(str(tagged_portrait(tmp_path / "p.jpg")))
        assert (panel._pixmap.width(), panel._pixmap.height()) == (20, 40)  # noqa: SLF001
    finally:
        panel.deleteLater()



class _IconWindow:
    @staticmethod
    def windowIcon():  # noqa: N802 — Qt's name
        return QIcon()


@pytest.fixture
def mirror(qapp, monkeypatch):
    """A mirror window whose show calls are recorded instead of shown."""
    win = MultiMonitorWindow(_IconWindow())
    win.shown = []
    monkeypatch.setattr(win, "showFullScreen", lambda: win.shown.append("full screen"))
    monkeypatch.setattr(win, "showMaximized", lambda: win.shown.append("maximised"))
    yield win
    win.deleteLater()


def _frameless(win) -> bool:
    return bool(win.windowFlags() & Qt.WindowType.FramelessWindowHint)


class TestPlacement:
    """The docs promised a frameless window; it opened framed and maximised everywhere."""

    def test_a_secondary_screen_gets_a_frameless_full_screen_mirror(self, mirror, monkeypatch):
        screen = QGuiApplication.screens()[0]
        monkeypatch.setattr(mod.QGuiApplication, "primaryScreen", staticmethod(lambda: None))
        mirror._show_on(screen)  # noqa: SLF001
        assert _frameless(mirror)
        assert mirror.shown == ["full screen"]
        assert mirror.windowHandle().screen() is screen
        assert mirror.geometry() == screen.geometry()

    def test_the_primary_screen_keeps_a_framed_window(self, mirror):
        """The main window lives there; a frameless full-screen mirror would bury it."""
        mirror._show_on(QGuiApplication.primaryScreen())  # noqa: SLF001
        assert not _frameless(mirror)
        assert mirror.shown == ["maximised"]

    def test_moving_back_to_the_primary_screen_restores_the_frame(self, mirror, monkeypatch):
        screen = QGuiApplication.primaryScreen()
        monkeypatch.setattr(mod.QGuiApplication, "primaryScreen", staticmethod(lambda: None))
        mirror._show_on(screen)  # noqa: SLF001
        monkeypatch.setattr(mod.QGuiApplication, "primaryScreen", staticmethod(lambda: screen))
        mirror._show_on(screen)  # noqa: SLF001
        assert not _frameless(mirror)
        assert mirror.shown == ["full screen", "maximised"]


class TestClosingKeys:
    @staticmethod
    def _press(win, key, mods=Qt.KeyboardModifier.NoModifier) -> list:
        closed = []
        win.closed.connect(lambda: closed.append(True))
        win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, mods))
        return closed

    def test_its_own_shortcut_closes_the_mirror(self, mirror):
        """The toast says Ctrl+Shift+M closes it, but the mirror holds the focus."""
        mods = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        assert self._press(mirror, Qt.Key.Key_M, mods) == [True]

    def test_escape_closes_the_mirror(self, mirror):
        assert self._press(mirror, Qt.Key.Key_Escape) == [True]

    def test_a_plain_m_does_not(self, mirror):
        assert self._press(mirror, Qt.Key.Key_M) == []
