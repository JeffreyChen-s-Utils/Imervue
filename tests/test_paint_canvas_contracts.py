"""Contracts for the PaintCanvas document binding and GL lifecycle paths.

The methods run unbound on a lightweight host object, so no QOpenGLWidget is
built and the file runs on headless CI. GL entry points are patched on the
module that owns the method under test, wherever it lives.
"""
from __future__ import annotations

import sys

import numpy as np
import pytest

from Imervue.paint.canvas import PaintCanvas
from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.damage import DamageRect
from Imervue.paint.document import PaintDocument


class _Signal:
    def __init__(self) -> None:
        self.emitted: list[tuple] = []

    def emit(self, *args) -> None:
        self.emitted.append(args)


class _Timer:
    def __init__(self) -> None:
        self.running = False
        self.starts = 0
        self.stops = 0

    def start(self) -> None:
        self.running = True
        self.starts += 1

    def stop(self) -> None:
        self.running = False
        self.stops += 1


class _Host:
    """Just enough PaintCanvas state for the document / lifecycle methods."""

    new_blank_document = PaintCanvas.new_blank_document
    load_image = PaintCanvas.load_image
    document = PaintCanvas.document
    set_document = PaintCanvas.set_document
    current_image = PaintCanvas.current_image
    current_selection = PaintCanvas.current_selection
    invalidate_texture = PaintCanvas.invalidate_texture
    _on_document_changed = PaintCanvas._on_document_changed
    set_selection = PaintCanvas.set_selection
    _maybe_refit_view = PaintCanvas._maybe_refit_view
    _deferred_fit_after_show = PaintCanvas._deferred_fit_after_show
    resizeGL = PaintCanvas.resizeGL
    _upload_texture = PaintCanvas._upload_texture

    def __init__(self, size: tuple[int, int] = (300, 200)) -> None:
        self._document = PaintDocument()
        self.unsubscribed = 0
        self._document_unsubscribe = self._count_unsubscribe
        self._needs_upload = False
        self._pending_damage = DamageRect(1, 1, 2, 2)
        self._marquee_segments = "stale"
        self._marquee_timer = _Timer()
        self._user_view_locked = True
        self._rotation_deg = 30.0
        self._fit_pending = False
        self._fitted_widget_size = (0, 0)
        self._last_resize_size = (0, 0)
        self._texture = None
        self._size = size
        self.image_loaded = _Signal()
        self.document_changed = _Signal()
        self.updates = 0
        self.fits: list = []

    def _count_unsubscribe(self) -> None:
        self.unsubscribed += 1

    def update(self) -> None:
        self.updates += 1

    def width(self) -> int:
        return self._size[0]

    def height(self) -> int:
        return self._size[1]

    def _reset_view_to_fit(self, widget_size=None) -> None:
        self.fits.append(widget_size)


def _rgba(h: int = 4, w: int = 6, value: int = 9) -> np.ndarray:
    return np.full((h, w, 4), value, dtype=np.uint8)


def _owner(name: str):
    """Module that defines ``PaintCanvas.<name>`` (where its GL globals live)."""
    return sys.modules[getattr(PaintCanvas, name).__module__]


# ---- document binding ---------------------------------------------------


def test_load_image_none_resets_to_an_empty_document():
    host = _Host()
    old = host._document
    PaintCanvas.load_image(host, None)
    assert host.unsubscribed == 1
    assert host._document is not old
    assert host._document.shape is None
    assert host._needs_upload is True
    assert host._pending_damage is EMPTY_DAMAGE
    assert host._marquee_segments is None
    assert host._marquee_timer.stops == 1
    assert host._user_view_locked is False
    assert host._rotation_deg == pytest.approx(0.0)
    assert host.updates == 1
    assert host.fits == []
    assert host.image_loaded.emitted == []
    assert host.document_changed.emitted == []


def test_load_image_none_subscribes_the_new_document():
    host = _Host()
    PaintCanvas.load_image(host, None)
    host._needs_upload = False
    host._pending_damage = DamageRect(0, 0, 1, 1)
    host._document.load_image(_rgba())
    assert host._needs_upload is True
    assert host._pending_damage is EMPTY_DAMAGE


@pytest.mark.parametrize("arr", [
    np.zeros((4, 4, 3), dtype=np.uint8),
    np.zeros((4, 4), dtype=np.uint8),
    np.zeros((4, 4, 4), dtype=np.float32),
])
def test_load_image_rejects_non_rgba_uint8(arr):
    host = _Host()
    with pytest.raises(ValueError, match="PaintCanvas.load_image expects HxWx4 uint8 RGBA"):
        PaintCanvas.load_image(host, arr)
    assert host.unsubscribed == 0


def test_load_image_binds_fits_and_signals():
    host = _Host()
    arr = _rgba(h=5, w=7)
    PaintCanvas.load_image(host, arr)
    assert host.unsubscribed == 1
    assert host._document.shape == (5, 7)
    assert host._marquee_segments is None
    assert host._marquee_timer.stops == 1
    assert host._needs_upload is True
    assert host._pending_damage is EMPTY_DAMAGE
    assert host._user_view_locked is False
    # Rotation is left alone on a real load (only a clear resets it).
    assert host._rotation_deg == pytest.approx(30.0)
    assert host.fits == [None]
    assert host.image_loaded.emitted == [(7, 5)]
    assert host.document_changed.emitted == [()]
    # One repaint from the document listener, one explicit.
    assert host.updates == 2
    np.testing.assert_array_equal(PaintCanvas.current_image(host), arr)


def test_new_blank_document_fills_every_pixel():
    host = _Host()
    PaintCanvas.new_blank_document(host, width=3, height=2, fill=(1, 2, 3, 4))
    img = PaintCanvas.current_image(host)
    assert img.shape == (2, 3, 4)
    assert (img == np.array([1, 2, 3, 4], dtype=np.uint8)).all()
    assert host.image_loaded.emitted == [(3, 2)]


def test_new_blank_document_defaults_are_1024_white():
    host = _Host()
    PaintCanvas.new_blank_document(host)
    img = PaintCanvas.current_image(host)
    assert img.shape == (1024, 1024, 4)
    assert (img == 255).all()


@pytest.mark.parametrize(("width", "height"), [(0, 4), (4, 0), (-1, 4)])
def test_new_blank_document_rejects_non_positive_size(width, height):
    with pytest.raises(ValueError, match="canvas size must be positive"):
        PaintCanvas.new_blank_document(_Host(), width=width, height=height)


@pytest.mark.parametrize("fill", [(0, 0, 0), (0, 0, 0, 256), (-1, 0, 0, 0), (0, 0, 0, 0, 0)])
def test_new_blank_document_rejects_bad_fill(fill):
    with pytest.raises(ValueError, match="fill must be a 4-tuple"):
        PaintCanvas.new_blank_document(_Host(), width=2, height=2, fill=fill)


def test_new_blank_document_accepts_fill_boundaries():
    host = _Host()
    PaintCanvas.new_blank_document(host, width=1, height=1, fill=(0, 255, 0, 255))
    assert PaintCanvas.current_image(host).tolist() == [[[0, 255, 0, 255]]]


def test_set_document_same_document_is_a_no_op():
    host = _Host()
    PaintCanvas.set_document(host, host._document)
    assert host.unsubscribed == 0
    assert host.updates == 0
    assert host._needs_upload is False


def test_set_document_swaps_and_emits_shape():
    host = _Host()
    doc = PaintDocument()
    doc.load_image(_rgba(h=3, w=8))
    PaintCanvas.set_document(host, doc)
    assert PaintCanvas.document(host) is doc
    assert host.unsubscribed == 1
    assert host._marquee_segments is None
    assert host._marquee_timer.stops == 1
    assert host._needs_upload is True
    assert host._pending_damage is EMPTY_DAMAGE
    assert host.image_loaded.emitted == [(8, 3)]
    assert host.updates == 1
    # No view refit and no document_changed on a page swap.
    assert host.fits == []
    assert host.document_changed.emitted == []


def test_set_document_empty_document_emits_nothing():
    host = _Host()
    PaintCanvas.set_document(host, PaintDocument())
    assert host.image_loaded.emitted == []
    assert host.updates == 1


def test_set_document_subscribes_the_new_document():
    host = _Host()
    doc = PaintDocument()
    PaintCanvas.set_document(host, doc)
    host._needs_upload = False
    doc.load_image(_rgba())
    assert host._needs_upload is True


def test_current_image_none_without_layers():
    assert PaintCanvas.current_image(_Host()) is None


def test_invalidate_texture_marks_full_upload_without_repaint():
    host = _Host()
    PaintCanvas.invalidate_texture(host)
    assert host._needs_upload is True
    assert host._pending_damage is EMPTY_DAMAGE
    assert host.updates == 0


def test_document_change_marks_full_upload_and_repaints():
    host = _Host()
    PaintCanvas._on_document_changed(host)
    assert host._needs_upload is True
    assert host._pending_damage is EMPTY_DAMAGE
    assert host.updates == 1


# ---- selection ----------------------------------------------------------


def test_set_selection_none_clears_marquee():
    host = _Host()
    PaintCanvas.load_image(host, _rgba())
    host._marquee_timer = _Timer()
    PaintCanvas.set_selection(host, None)
    assert PaintCanvas.current_selection(host) is None
    assert host._marquee_segments is None
    assert host._marquee_timer.stops == 1
    assert host._marquee_timer.starts == 0


def test_set_selection_with_outline_starts_marquee():
    host = _Host()
    PaintCanvas.load_image(host, _rgba())
    host._marquee_timer = _Timer()
    updates = host.updates
    mask = np.zeros((4, 6), dtype=bool)
    mask[1:3, 1:4] = True
    PaintCanvas.set_selection(host, mask)
    assert host._marquee_segments.shape[0] > 0
    assert host._marquee_timer.starts == 1
    assert host._marquee_timer.running is True
    # The document's selection notify repaints too, then the explicit one.
    assert host.updates == updates + 2
    np.testing.assert_array_equal(PaintCanvas.current_selection(host), mask)


def test_set_selection_empty_mask_stops_marquee():
    host = _Host()
    PaintCanvas.load_image(host, _rgba())
    host._marquee_timer = _Timer()
    PaintCanvas.set_selection(host, np.zeros((4, 6), dtype=bool))
    assert host._marquee_segments.shape[0] == 0
    assert host._marquee_timer.stops == 1
    assert host._marquee_timer.starts == 0


@pytest.mark.parametrize("mask", [
    np.zeros((4, 6), dtype=np.uint8),
    np.zeros((4, 6, 1), dtype=bool),
])
def test_set_selection_rejects_non_bool_2d(mask):
    host = _Host()
    with pytest.raises(ValueError, match="selection mask must be HxW bool"):
        PaintCanvas.set_selection(host, mask)
    assert host.updates == 0


# ---- view fit lifecycle -------------------------------------------------


def test_refit_uses_widget_size_when_never_resized():
    host = _Host(size=(120, 80))
    host._user_view_locked = False
    PaintCanvas._maybe_refit_view(host)
    assert host.fits == [(120, 80)]


def test_refit_skipped_for_degenerate_widget():
    host = _Host(size=(0, 80))
    host._fit_pending = True
    PaintCanvas._maybe_refit_view(host)
    assert host.fits == []


def test_refit_skipped_when_locked_and_not_pending():
    host = _Host()
    host._last_resize_size = (50, 40)
    PaintCanvas._maybe_refit_view(host)
    assert host.fits == []


def test_refit_forced_by_pending_even_when_locked():
    host = _Host()
    host._last_resize_size = (50, 40)
    host._fit_pending = True
    PaintCanvas._maybe_refit_view(host)
    assert host.fits == [(50, 40)]


def test_refit_skipped_when_size_already_fitted():
    host = _Host()
    host._user_view_locked = False
    host._last_resize_size = (50, 40)
    host._fitted_widget_size = (50, 40)
    PaintCanvas._maybe_refit_view(host)
    assert host.fits == []


def test_deferred_fit_degenerate_keeps_pending():
    host = _Host(size=(0, 0))
    host._fit_pending = True
    PaintCanvas._deferred_fit_after_show(host)
    assert host._fit_pending is True
    assert host.fits == []
    assert host.updates == 0


def test_deferred_fit_locked_view_clears_pending_only():
    host = _Host()
    host._fit_pending = True
    PaintCanvas._deferred_fit_after_show(host)
    assert host._fit_pending is False
    assert host.fits == []


def test_deferred_fit_prefers_last_resize_size():
    host = _Host(size=(999, 999))
    host._user_view_locked = False
    host._last_resize_size = (64, 32)
    PaintCanvas._deferred_fit_after_show(host)
    assert host.fits == [(64, 32)]
    assert host.updates == 1


def _patch_resize_gl(monkeypatch, calls):
    mod = _owner("resizeGL")
    for name in ("glViewport", "glMatrixMode", "glLoadIdentity", "glOrtho"):
        monkeypatch.setattr(mod, name, lambda *a, _n=name: calls.append((_n, a)))


def test_resize_gl_uses_logical_ortho_and_device_viewport(monkeypatch):
    calls: list = []
    _patch_resize_gl(monkeypatch, calls)
    host = _Host(size=(100, 50))
    PaintCanvas.resizeGL(host, 200, 0)
    mod = _owner("resizeGL")
    assert ("glViewport", (0, 0, 200, 1)) in calls
    assert ("glOrtho", (0, 100, 50, 0, -1, 1)) in calls
    assert calls[-1] == ("glMatrixMode", (mod.GL_MODELVIEW,))
    assert host._last_resize_size == (100, 50)
    # View is locked and no fit is pending: no refit.
    assert host.fits == []


def test_resize_gl_refits_until_user_locks_view(monkeypatch):
    _patch_resize_gl(monkeypatch, [])
    host = _Host(size=(0, 0))
    host._user_view_locked = False
    PaintCanvas.resizeGL(host, 10, 10)
    assert host._last_resize_size == (1, 1)
    assert host.fits == [(1, 1)]


def test_resize_gl_refits_when_pending(monkeypatch):
    _patch_resize_gl(monkeypatch, [])
    host = _Host(size=(30, 20))
    host._fit_pending = True
    PaintCanvas.resizeGL(host, 30, 20)
    assert host.fits == [(30, 20)]


# ---- texture upload ------------------------------------------------------


def _patch_upload_gl(monkeypatch, calls):
    mod = _owner("_upload_texture")
    for name in ("glBindTexture", "glTexParameteri", "glTexParameterf",
                 "glTexImage2D", "glTexSubImage2D", "glDeleteTextures"):
        monkeypatch.setattr(mod, name, lambda *a, _n=name: calls.append((_n, a)))
    monkeypatch.setattr(mod, "glGenTextures", lambda _n: 11)


def test_upload_none_deletes_existing_texture(monkeypatch):
    calls: list = []
    _patch_upload_gl(monkeypatch, calls)
    host = _Host()
    host._texture = 4
    PaintCanvas._upload_texture(host, None)
    assert calls == [("glDeleteTextures", (1, [4]))]
    assert host._texture is None


def test_upload_none_without_texture_is_a_no_op(monkeypatch):
    calls: list = []
    _patch_upload_gl(monkeypatch, calls)
    host = _Host()
    PaintCanvas._upload_texture(host, None)
    assert calls == []


def test_first_upload_generates_and_configures_texture(monkeypatch):
    calls: list = []
    _patch_upload_gl(monkeypatch, calls)
    host = _Host()
    PaintCanvas._upload_texture(host, _rgba(h=4, w=6))
    names = [c[0] for c in calls]
    assert host._texture == 11
    assert names.count("glTexParameteri") == 2
    assert names.count("glTexParameterf") == 2
    assert "glTexImage2D" in names
    assert "glTexSubImage2D" not in names
    assert calls[-1] == ("glBindTexture", (_owner("_upload_texture").GL_TEXTURE_2D, 0))
    assert host._pending_damage is EMPTY_DAMAGE


def test_partial_damage_reuses_texture_with_sub_upload(monkeypatch):
    calls: list = []
    _patch_upload_gl(monkeypatch, calls)
    host = _Host()
    host._texture = 3
    host._pending_damage = DamageRect(1, 1, 2, 2)
    PaintCanvas._upload_texture(host, _rgba(h=4, w=6))
    names = [c[0] for c in calls]
    assert host._texture == 3
    assert "glTexParameteri" not in names
    assert "glTexImage2D" not in names
    sub = next(c[1] for c in calls if c[0] == "glTexSubImage2D")
    assert sub[2:6] == (1, 1, 2, 2)
    assert len(sub[-1]) == 2 * 2 * 4
    assert host._pending_damage is EMPTY_DAMAGE


def test_damage_outside_frame_falls_back_to_full_upload(monkeypatch):
    calls: list = []
    _patch_upload_gl(monkeypatch, calls)
    host = _Host()
    host._texture = 3
    host._pending_damage = DamageRect(50, 50, 4, 4)
    PaintCanvas._upload_texture(host, _rgba(h=4, w=6))
    names = [c[0] for c in calls]
    assert "glTexImage2D" in names
    assert "glTexSubImage2D" not in names
