"""Tests for GPUImageView._apply_initial_view — the deep-zoom sizing fix.

The bug: a low-res progressive preview fits itself into ``view.zoom`` while
the full image loads, so reading ``view.zoom`` when the full image lands gave
the preview's placeholder fit, not this image's remembered view — the full
image displayed at the wrong size. ``_apply_initial_view`` re-restores the
image's own saved view *before* the fit-or-keep decision so the clobbered
zoom can't drive it.

``GPUImageView`` is a ``QOpenGLWidget``; constructing one needs a GL surface
(and trips the headless-CI crash). These tests never construct it — they call
the method unbound on a light duck-typed fake, so no widget and no GL context
are created and the file must run on CI.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.gpu_image_view import GPUImageView


def _fake(*, path="img.png", should_refit=True):
    calls: list = []
    fake = SimpleNamespace(
        _current_path=lambda: path,
        _restore_view_state=lambda p: calls.append(("restore", p)),
        _should_refit_on_load=lambda: should_refit,
        _fit_to_window=lambda: calls.append(("fit",)),
        _schedule_settle_refit=lambda: calls.append(("settle",)),
    )
    return fake, calls


def test_restores_remembered_view_before_deciding():
    # The restore MUST run before the fit decision, so a preview's leftover
    # zoom is overwritten with the image's own remembered view first. A fresh
    # fit also queues the deferred settle re-fit (filmstrip / layout settling).
    fake, calls = _fake(should_refit=True)
    GPUImageView._apply_initial_view(fake)
    assert calls == [("restore", "img.png"), ("fit",), ("settle",)]


def test_keeps_remembered_zoom_in_without_fitting():
    # A genuine remembered zoom-in → restore it, do NOT re-fit, and do NOT
    # queue a settle re-fit that would snap the zoom-in back.
    fake, calls = _fake(should_refit=False)
    GPUImageView._apply_initial_view(fake)
    assert calls == [("restore", "img.png")]  # restored, not re-fit


def test_no_current_path_is_a_noop():
    calls: list = []
    fake = SimpleNamespace(
        _current_path=lambda: None,
        _restore_view_state=lambda p: calls.append(("restore", p)),
        _should_refit_on_load=lambda: True,
        _fit_to_window=lambda: calls.append(("fit",)),
        _schedule_settle_refit=lambda: calls.append(("settle",)),
    )
    GPUImageView._apply_initial_view(fake)
    assert calls == []


def test_restore_target_is_the_current_path():
    fake, calls = _fake(path="folder/sub/photo.cr2", should_refit=False)
    GPUImageView._apply_initial_view(fake)
    assert calls == [("restore", "folder/sub/photo.cr2")]
