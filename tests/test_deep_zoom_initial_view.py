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
        _schedule_load_settle_refit=lambda: calls.append(("load-settle",)),
        _browse=SimpleNamespace(clamp_pan=lambda: calls.append(("clamp",))),
        _user_locked_view=False,
    )
    return fake, calls


def test_restores_remembered_view_before_deciding():
    # The restore MUST run before the fit decision, so a preview's leftover
    # zoom is overwritten with the image's own remembered view first. A fresh
    # fit also queues BOTH deferred confirmations: the singleShot(0) chain that
    # drains Qt's queued layout, and the real-interval watch that spans a canvas
    # settling slower than that (without which paging on before the correction
    # lands just re-derives the same wrong fit from the same unsettled canvas).
    fake, calls = _fake(should_refit=True)
    GPUImageView._apply_initial_view(fake)
    assert calls == [
        ("restore", "img.png"), ("fit",), ("settle",), ("load-settle",),
    ]


def test_keeps_remembered_zoom_in_without_fitting():
    # A genuine remembered zoom-in → restore it, do NOT re-fit, and do NOT
    # queue a settle re-fit that would snap the zoom-in back. But clamp its pan
    # on-screen and lock the view so the next resize can't refit it away.
    fake, calls = _fake(should_refit=False)
    GPUImageView._apply_initial_view(fake)
    assert calls == [("restore", "img.png"), ("clamp",)]  # restored, clamped
    assert fake._user_locked_view is True


def test_no_current_path_is_a_noop():
    calls: list = []
    fake = SimpleNamespace(
        _current_path=lambda: None,
        _restore_view_state=lambda p: calls.append(("restore", p)),
        _should_refit_on_load=lambda: True,
        _fit_to_window=lambda: calls.append(("fit",)),
        _schedule_settle_refit=lambda: calls.append(("settle",)),
        _schedule_load_settle_refit=lambda: calls.append(("load-settle",)),
    )
    GPUImageView._apply_initial_view(fake)
    assert calls == []


def test_restore_target_is_the_current_path():
    fake, calls = _fake(path="folder/sub/photo.cr2", should_refit=False)
    GPUImageView._apply_initial_view(fake)
    assert calls == [("restore", "folder/sub/photo.cr2"), ("clamp",)]


def test_settle_refit_skips_when_a_newer_image_was_requested():
    # A settle queued for an earlier image must not fit the current one — that
    # is what clobbered a quick keyboard switch's remembered zoom-in.
    fits: list = []
    fake = SimpleNamespace(
        _deep_zoom_request_id=5,
        deep_zoom=object(),
        _user_locked_view=False,
        _fit_to_window=lambda: fits.append("fit"),
    )
    GPUImageView._settle_refit(fake, 4)   # stale → skip
    assert fits == []
    GPUImageView._settle_refit(fake, 5)   # current → fit
    assert fits == ["fit"]


def test_settle_refit_skips_when_user_locked_even_if_current():
    fits: list = []
    fake = SimpleNamespace(
        _deep_zoom_request_id=3,
        deep_zoom=object(),
        _user_locked_view=True,           # a deliberate zoom-in
        _fit_to_window=lambda: fits.append("fit"),
    )
    GPUImageView._settle_refit(fake, 3)
    assert fits == []
