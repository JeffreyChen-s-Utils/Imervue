"""Tests for the deep-zoom display-finalization and prefetch completion paths.

``GPUImageView`` is a ``QOpenGLWidget`` (constructing one needs a GL surface and
trips the headless-CI crash), so these call the methods unbound on light
duck-typed fakes — no widget, no GL context — the same approach as
``test_deep_zoom_initial_view``.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.gpu_image_view import GPUImageView


# ---------------------------------------------------------------------------
# _finalize_deep_zoom_display — the shared tail all three display paths run
# ---------------------------------------------------------------------------

def _display_fake(*, with_issue_hook=True):
    calls: list = []
    main_window = SimpleNamespace()
    if with_issue_hook:
        main_window.clear_image_issue = lambda p: calls.append(("clear_issue", p))
    fake = SimpleNamespace(
        _deep_zoom_loading="pending",
        _deep_zoom_error=("pending", "boom"),
        _deep_zoom_retry_counts={"img.png": 2, "other.png": 1},
        main_window=main_window,
        enforce_memory_pressure=lambda: calls.append(("enforce",)),
        _apply_initial_view=lambda: calls.append(("apply_view",)),
        _init_animation=lambda p: calls.append(("anim", p)),
        _prefetch_neighbors=lambda: calls.append(("prefetch",)),
        _update_status_info=lambda: calls.append(("status",)),
        _notify_deep_zoom_displayed=lambda: calls.append(("notify",)),
        _browse=SimpleNamespace(begin_image_fade_in=lambda: calls.append(("fade",))),
        update=lambda: calls.append(("update",)),
    )
    return fake, calls


def test_finalize_clears_state_and_runs_every_display_step():
    fake, calls = _display_fake()
    GPUImageView._finalize_deep_zoom_display(fake, "img.png")
    assert fake._deep_zoom_loading is None
    assert fake._deep_zoom_error is None
    assert "img.png" not in fake._deep_zoom_retry_counts  # this image's retries reset
    assert fake._deep_zoom_retry_counts == {"other.png": 1}  # others untouched
    assert [c[0] for c in calls] == [
        "clear_issue", "enforce", "apply_view", "anim",
        "prefetch", "status", "notify", "fade", "update",
    ]
    # Animation is started for THIS path (the promoted-prefetch drift bug).
    assert ("anim", "img.png") in calls


def test_finalize_without_issue_hook_still_runs_the_rest():
    fake, calls = _display_fake(with_issue_hook=False)
    GPUImageView._finalize_deep_zoom_display(fake, "img.png")
    assert [c[0] for c in calls] == [
        "enforce", "apply_view", "anim", "prefetch",
        "status", "notify", "fade", "update",
    ]


# ---------------------------------------------------------------------------
# _on_prefetch_loaded — promote-vs-store
# ---------------------------------------------------------------------------

def _prefetch_fake(*, images, current, deep_zoom, loading):
    calls: list = []
    return SimpleNamespace(
        _prefetch=SimpleNamespace(
            pop_worker=lambda p: calls.append(("pop", p)),
            store=lambda p, d: calls.append(("store", p)),
        ),
        model=SimpleNamespace(images=list(images)),
        current_index=current,
        deep_zoom=deep_zoom,
        tile_manager=None,
        _deep_zoom_loading=loading,
        _finalize_deep_zoom_display=lambda p: calls.append(("finalize", p)),
    ), calls


def test_prefetch_loaded_promotes_and_finalizes_when_primary():
    fake, calls = _prefetch_fake(
        images=["a", "b"], current=1, deep_zoom=None, loading="b")
    GPUImageView._on_prefetch_loaded(fake, object(), "b")
    assert fake.deep_zoom is not None          # displayed
    assert fake.tile_manager is not None
    assert ("finalize", "b") in calls
    assert not any(c[0] == "store" for c in calls)  # not shelved to cache


def test_prefetch_loaded_relocates_index_when_list_reordered():
    fake, calls = _prefetch_fake(
        images=["b", "a"], current=0, deep_zoom=None, loading="a")
    GPUImageView._on_prefetch_loaded(fake, object(), "a")
    assert fake.current_index == 1             # re-anchored to a's new row
    assert ("finalize", "a") in calls


def test_prefetch_loaded_stores_when_not_the_primary_load():
    # deep_zoom already showing → this is a genuine neighbour prefetch → cache it.
    fake, calls = _prefetch_fake(
        images=["a", "b"], current=0, deep_zoom=object(), loading=None)
    GPUImageView._on_prefetch_loaded(fake, object(), "b")
    assert ("store", "b") in calls
    assert not any(c[0] == "finalize" for c in calls)


def test_prefetch_loaded_stores_when_waiting_on_a_different_image():
    fake, calls = _prefetch_fake(
        images=["a", "b"], current=0, deep_zoom=None, loading="a")
    GPUImageView._on_prefetch_loaded(fake, object(), "b")  # b arrived, waiting on a
    assert ("store", "b") in calls
    assert not any(c[0] == "finalize" for c in calls)


# ---------------------------------------------------------------------------
# _on_prefetch_error — the stuck-"Loading…" fix
# ---------------------------------------------------------------------------

def _error_fake(*, deep_zoom, loading, request_id=7):
    calls: list = []
    return SimpleNamespace(
        _prefetch=SimpleNamespace(pop_worker=lambda p: calls.append(("pop", p))),
        deep_zoom=deep_zoom,
        _deep_zoom_loading=loading,
        _deep_zoom_request_id=request_id,
        _on_deep_zoom_failed=lambda p, m, r: calls.append(("fail", p, m, r)),
    ), calls


def test_prefetch_error_routes_to_failure_when_it_is_the_primary_load():
    fake, calls = _error_fake(deep_zoom=None, loading="b", request_id=7)
    GPUImageView._on_prefetch_error(fake, "b", "decode failed")
    assert ("pop", "b") in calls
    assert ("fail", "b", "decode failed", 7) in calls  # surfaced, not stuck


def test_prefetch_error_only_pops_when_an_image_is_already_shown():
    fake, calls = _error_fake(deep_zoom=object(), loading=None)
    GPUImageView._on_prefetch_error(fake, "b", "decode failed")
    assert ("pop", "b") in calls
    assert not any(c[0] == "fail" for c in calls)


def test_prefetch_error_only_pops_when_waiting_on_a_different_image():
    fake, calls = _error_fake(deep_zoom=None, loading="a")
    GPUImageView._on_prefetch_error(fake, "b", "decode failed")
    assert ("pop", "b") in calls
    assert not any(c[0] == "fail" for c in calls)
