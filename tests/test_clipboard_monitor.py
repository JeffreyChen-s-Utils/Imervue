"""
Tests for ClipboardMonitor — clipboard listening + dedup + enable gate.

Uses the session-scoped ``qapp`` fixture from conftest. Each test cleans up
its own clipboard state in case the test runner shares the system clipboard.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from Imervue.system.clipboard_monitor import (
    SETTING_KEY, ClipboardMonitor, _qimage_to_pil,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


def _pil_to_qimage(img: Image.Image) -> QImage:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    q = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return q.copy()


@pytest.fixture
def fresh_clipboard(qapp):
    """Snapshot and restore clipboard state around each test."""
    cb = QApplication.clipboard()
    saved = cb.image() if cb is not None else None
    cb.clear()
    yield cb
    cb.clear()
    if saved is not None and not saved.isNull():
        cb.setImage(saved)


@pytest.fixture
def reset_setting():
    """Snapshot and restore the monitor's persisted setting."""
    saved = user_setting_dict.get(SETTING_KEY)
    user_setting_dict.pop(SETTING_KEY, None)
    yield
    if saved is None:
        user_setting_dict.pop(SETTING_KEY, None)
    else:
        user_setting_dict[SETTING_KEY] = saved


class TestQImagePilConversion:
    def test_round_trip_preserves_pixels(self, qapp):
        arr = np.zeros((20, 30, 4), dtype=np.uint8)
        arr[..., 0] = 200  # red
        arr[..., 3] = 255
        original = Image.fromarray(arr, "RGBA")
        q = _pil_to_qimage(original)
        restored = _qimage_to_pil(q)
        assert restored.size == original.size
        assert restored.mode == "RGBA"
        assert np.array_equal(np.array(restored), arr)

    def test_handles_solid_color(self, qapp):
        arr = np.full((10, 10, 4), 128, dtype=np.uint8)
        arr[..., 3] = 255
        q = _pil_to_qimage(Image.fromarray(arr, "RGBA"))
        restored = _qimage_to_pil(q)
        assert (np.array(restored)[..., 0] == 128).all()


class TestClipboardMonitorState:
    def test_starts_disabled_by_default(self, qapp, reset_setting):
        m = ClipboardMonitor()
        assert m.is_enabled() is False

    def test_setting_persists(self, qapp, reset_setting):
        m = ClipboardMonitor()
        m.set_enabled(True)
        assert user_setting_dict[SETTING_KEY] is True
        m.set_enabled(False)
        assert user_setting_dict[SETTING_KEY] is False

    def test_restored_from_setting(self, qapp, reset_setting):
        user_setting_dict[SETTING_KEY] = True
        m = ClipboardMonitor()
        assert m.is_enabled() is True

    def test_toggle(self, qapp, reset_setting):
        m = ClipboardMonitor()
        assert m.is_enabled() is False
        assert m.toggle() is True
        assert m.is_enabled() is True
        assert m.toggle() is False

    def test_set_same_value_is_noop(self, qapp, reset_setting):
        m = ClipboardMonitor()
        m.set_enabled(False)
        m.set_enabled(False)
        # Last hash sentinel still cleared (None) — no exception
        assert m._last_hash is None


class TestClipboardMonitorDedup:
    def test_disabled_does_not_emit(self, qapp, fresh_clipboard, reset_setting):
        m = ClipboardMonitor()
        captured: list = []
        m.image_captured.connect(captured.append)

        # Force a clipboard change while disabled
        arr = np.full((5, 5, 4), 100, dtype=np.uint8)
        arr[..., 3] = 255
        fresh_clipboard.setImage(_pil_to_qimage(Image.fromarray(arr, "RGBA")))
        qapp.processEvents()

        assert captured == []

    def test_enabled_emits_on_image(self, qapp, fresh_clipboard, reset_setting):
        m = ClipboardMonitor()
        m.set_enabled(True)
        captured: list = []
        m.image_captured.connect(captured.append)

        arr = np.zeros((10, 10, 4), dtype=np.uint8)
        arr[..., 1] = 255  # green
        arr[..., 3] = 255
        fresh_clipboard.setImage(_pil_to_qimage(Image.fromarray(arr, "RGBA")))
        qapp.processEvents()

        assert len(captured) == 1
        pil = captured[0]
        assert isinstance(pil, Image.Image)
        assert pil.size == (10, 10)
        assert np.array(pil)[5, 5, 1] == 255

    def test_dedup_suppresses_repeat_of_same_image(
        self, qapp, fresh_clipboard, reset_setting
    ):
        m = ClipboardMonitor()
        m.set_enabled(True)
        captured: list = []
        m.image_captured.connect(captured.append)

        arr = np.full((8, 8, 4), 200, dtype=np.uint8)
        arr[..., 3] = 255
        img = _pil_to_qimage(Image.fromarray(arr, "RGBA"))

        fresh_clipboard.setImage(img)
        qapp.processEvents()
        fresh_clipboard.setImage(img)
        qapp.processEvents()

        # The second identical image must not re-emit
        assert len(captured) == 1

    def test_different_image_emits_again(
        self, qapp, fresh_clipboard, reset_setting
    ):
        m = ClipboardMonitor()
        m.set_enabled(True)
        captured: list = []
        m.image_captured.connect(captured.append)

        a = np.full((8, 8, 4), 50, dtype=np.uint8)
        a[..., 3] = 255
        b = np.full((8, 8, 4), 150, dtype=np.uint8)
        b[..., 3] = 255
        fresh_clipboard.setImage(_pil_to_qimage(Image.fromarray(a, "RGBA")))
        qapp.processEvents()
        fresh_clipboard.setImage(_pil_to_qimage(Image.fromarray(b, "RGBA")))
        qapp.processEvents()

        assert len(captured) == 2

    def test_re_enable_resets_dedup(
        self, qapp, fresh_clipboard, reset_setting
    ):
        """After toggling off→on the same image should fire again — the
        user has explicitly asked us to start watching, so suppression
        based on a stale hash from a prior session would surprise them."""
        m = ClipboardMonitor()
        m.set_enabled(True)
        captured: list = []
        m.image_captured.connect(captured.append)

        arr = np.full((8, 8, 4), 90, dtype=np.uint8)
        arr[..., 3] = 255
        img = _pil_to_qimage(Image.fromarray(arr, "RGBA"))
        fresh_clipboard.setImage(img)
        qapp.processEvents()
        assert len(captured) == 1

        m.set_enabled(False)
        m.set_enabled(True)
        # Re-set to trigger another dataChanged after re-enabling
        fresh_clipboard.clear()
        qapp.processEvents()
        fresh_clipboard.setImage(img)
        qapp.processEvents()

        assert len(captured) == 2

    def test_text_clipboard_does_not_emit(
        self, qapp, fresh_clipboard, reset_setting
    ):
        m = ClipboardMonitor()
        m.set_enabled(True)
        captured: list = []
        m.image_captured.connect(captured.append)

        fresh_clipboard.setText("hello world")
        qapp.processEvents()

        assert captured == []


class TestGrabCurrentImage:
    def test_returns_none_when_clipboard_empty(
        self, qapp, fresh_clipboard, reset_setting
    ):
        m = ClipboardMonitor()
        assert m.grab_current_image() is None

    def test_returns_pil_when_image_present(
        self, qapp, fresh_clipboard, reset_setting
    ):
        m = ClipboardMonitor()
        arr = np.full((6, 6, 4), 77, dtype=np.uint8)
        arr[..., 3] = 255
        fresh_clipboard.setImage(_pil_to_qimage(Image.fromarray(arr, "RGBA")))
        qapp.processEvents()

        result = m.grab_current_image()
        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.size == (6, 6)

    def test_grab_works_even_when_disabled(
        self, qapp, fresh_clipboard, reset_setting
    ):
        """grab_current_image() is the explicit "Paste" path — must work
        regardless of the auto-monitor toggle."""
        m = ClipboardMonitor()
        assert m.is_enabled() is False
        arr = np.full((4, 4, 4), 33, dtype=np.uint8)
        arr[..., 3] = 255
        fresh_clipboard.setImage(_pil_to_qimage(Image.fromarray(arr, "RGBA")))
        qapp.processEvents()

        assert m.grab_current_image() is not None

    def test_grab_returns_none_for_text_clipboard(
        self, qapp, fresh_clipboard, reset_setting
    ):
        m = ClipboardMonitor()
        fresh_clipboard.setText("not an image")
        qapp.processEvents()
        assert m.grab_current_image() is None
