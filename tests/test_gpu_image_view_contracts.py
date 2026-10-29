"""Contract tests for :class:`GPUImageView` and its mixins.

They pin what the viewer must keep doing however its methods are spread over
modules: every Qt override still resolves ahead of ``QOpenGLWidget``, no mixin
grows an ``__init__``, the thin delegations reach their helper modules with the
same arguments, and the modify-panel / recipe-reload / bookmark / thumbnail-size
/ teardown paths keep their order and side effects. Every method is driven
unbound on a lightweight host, so no GL widget is ever built.
"""
from __future__ import annotations

import contextlib
import logging
import sys
import types
from types import SimpleNamespace

import pytest
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_QT_OVERRIDES = (
    "initializeGL", "paintGL", "resizeGL", "showEvent", "hideEvent",
    "keyPressEvent", "event", "leaveEvent",
    "dragEnterEvent", "dragMoveEvent", "dropEvent",
)

_EXTERNAL_CONTRACT = (
    "open_develop_panel", "set_cvd_view_mode", "reload_current_image_with_recipe",
    "_on_recipe_committed", "_update_status_info", "_toggle_bookmark",
    "_paste_image_from_clipboard", "_delete_all_tile_textures",
    "_evict_tile_textures_if_needed", "_clear_deep_zoom", "_cancel_tile_workers",
    "_cancel_deep_zoom_worker", "_cancel_all_prefetch", "set_thumbnail_size",
    "load_tile_grid_async", "run_shortcut_action", "add_thumbnail",
    "history_back", "history_forward", "jump_to_random_image",
    "_apply_cull_state", "_apply_color_label", "clear_tile_grid",
    "_clamp_grid_scroll", "_toast", "_current_path", "_init_animation",
    "_stop_animation", "_save_view_state", "_restore_view_state",
    "_current_minimap_rect", "_current_gl_context", "_ensure_tile_texture",
)


def _owner(name: str) -> type:
    return next(c for c in GPUImageView.__mro__ if name in c.__dict__)


def _bind(host, *names):
    for name in names:
        setattr(host, name, types.MethodType(getattr(GPUImageView, name), host))
    return host


def _recorder(log, label, result=None):
    def _record(*args, **kwargs):
        log.append((label, args, kwargs))
        return result
    return _record


# ---------------------------------------------------------------------------
# Class shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", _QT_OVERRIDES)
def test_qt_override_resolves_ahead_of_qopenglwidget(name):
    owner = _owner(name)
    assert owner.__module__.startswith("Imervue.gpu_image_view.")
    mro = GPUImageView.__mro__
    assert mro.index(owner) < mro.index(QOpenGLWidget)


@pytest.mark.parametrize("name", _EXTERNAL_CONTRACT)
def test_external_contract_method_still_resolves(name):
    owner = _owner(name)
    assert owner.__module__.startswith("Imervue.gpu_image_view.")
    assert callable(getattr(GPUImageView, name))


def test_qopenglwidget_is_the_last_base_and_mixins_add_no_init():
    assert GPUImageView.__bases__[-1] is QOpenGLWidget
    for base in GPUImageView.__bases__[:-1]:
        assert "__init__" not in base.__dict__, base.__name__
    assert "__init__" in GPUImageView.__dict__


def test_minimap_attributes_are_declared_on_the_class():
    assert GPUImageView._minimap_tex is None
    assert GPUImageView._minimap_dzi is None


# ---------------------------------------------------------------------------
# One-line delegations
# ---------------------------------------------------------------------------

_DELEGATIONS = [
    ("load_tile_grid_async", ("paths",), "tile_loader", "load_tile_grid_async",
     ("paths",)),
    ("_on_thumbnail_loaded", ("img", "p", 3), "tile_loader", "on_thumbnail_loaded",
     ("img", "p", 3)),
    ("_on_thumbnail_error", ("p", "msg", 3), "tile_loader", "on_thumbnail_error",
     ("p", "msg", 3)),
    ("_flush_thumbnail_progress", (), "tile_loader", "flush_thumbnail_progress", ()),
    ("_tick_offline_sweep", (), "tile_loader", "tick_offline_sweep", ()),
    ("_on_offline_scan_finished", ({"a"}, 2), "tile_loader",
     "on_offline_scan_finished", ({"a"}, 2, ())),
    ("_on_offline_scan_finished", ({"a"}, 2, ("b",)), "tile_loader",
     "on_offline_scan_finished", ({"a"}, 2, ("b",))),
    ("add_thumbnail", ("img", "p"), "tile_loader", "add_thumbnail",
     ("img", "p", None)),
    ("_ensure_filmstrip_thumbnail", ("p",), "tile_loader",
     "ensure_filmstrip_thumbnail", ("p",)),
    ("_on_filmstrip_thumbnail_loaded", ("img", "p", 1), "tile_loader",
     "on_filmstrip_thumbnail_loaded", ("img", "p", 1)),
    ("_update_hover_preview", ("ev",), "hover_preview_binding",
     "update_hover_preview", ("ev",)),
    ("_cancel_hover_preview", (), "hover_preview_binding", "cancel_hover_preview", ()),
    ("_apply_color_label", ("red",), "cull_actions", "apply_color_label", ("red",)),
    ("_apply_cull_state", ("pick",), "cull_actions", "apply_cull_state", ("pick",)),
    ("jump_to_random_image", (), "view_state", "jump_to_random", ()),
    ("_save_view_state", (), "view_state", "save_view_state", ()),
    ("_restore_view_state", ("p",), "view_state", "restore_view_state", ("p",)),
    ("_paste_image_from_clipboard", (), "clipboard_paste",
     "paste_image_from_clipboard", ()),
    ("_update_status_info", (), "status_info", "update_status_info", ()),
    ("_evict_tile_textures_if_needed", (), "tile_textures", "evict_if_needed", ()),
    ("_delete_all_tile_textures", (), "tile_textures", "delete_all_tile_textures", ()),
    ("_ensure_tile_texture", ("p", "img"), "tile_textures", "ensure_tile_texture",
     ("p", "img")),
]


@pytest.mark.parametrize(("method", "args", "module", "func", "expected"), _DELEGATIONS)
def test_delegation_reaches_its_helper(monkeypatch, method, args, module, func, expected):
    calls = []
    monkeypatch.setattr(f"Imervue.gpu_image_view.{module}.{func}",
                        _recorder(calls, func, "ret"))
    host = SimpleNamespace()
    result = getattr(GPUImageView, method)(host, *args)
    assert calls == [(func, (host, *expected), {})]
    if method == "_ensure_tile_texture":
        assert result == "ret"


def test_history_and_prefetch_and_shortcut_delegate_to_collaborators():
    calls = []
    host = SimpleNamespace(
        _history=SimpleNamespace(push=_recorder(calls, "push"),
                                 back=_recorder(calls, "back", True),
                                 forward=_recorder(calls, "forward", False)),
        _prefetch=SimpleNamespace(cancel_all=_recorder(calls, "cancel_all")),
        _key_dispatch=SimpleNamespace(dispatch=_recorder(calls, "dispatch")),
        _overlay=SimpleNamespace(paint=_recorder(calls, "paint"),
                                 tick_placeholder=_recorder(calls, "tick")),
        _deep_zoom_renderer=SimpleNamespace(
            current_minimap_rect=_recorder(calls, "rect", (1, 2, 3, 4))),
    )
    GPUImageView._push_history(host, "a")
    assert GPUImageView.history_back(host) is True
    assert GPUImageView.history_forward(host) is False
    GPUImageView._cancel_all_prefetch(host)
    GPUImageView.run_shortcut_action(host, "undo")
    GPUImageView._paint_overlay(host, "painter")
    GPUImageView._tick_placeholder(host)
    assert GPUImageView._current_minimap_rect(host) == (1, 2, 3, 4)
    assert [c[0] for c in calls] == [
        "push", "back", "forward", "cancel_all", "dispatch", "paint", "tick", "rect"]
    assert calls[0][1] == ("a",)
    assert calls[4][1] == ("undo",)
    assert calls[5][1] == ("painter",)


def test_reload_rewritten_image_refreshes_tile_row_and_image(monkeypatch):
    calls = []
    monkeypatch.setattr("Imervue.gpu_image_view.tile_loader.refresh_rewritten_tile",
                        _recorder(calls, "tile"))
    monkeypatch.setattr("Imervue.gpu_image_view.tile_loader.refetch_list_rows",
                        _recorder(calls, "rows"))
    host = SimpleNamespace(_load_generation=7)
    host.reload_current_image_with_recipe = _recorder(calls, "reload")
    GPUImageView._reload_rewritten_image(host, "p")
    assert calls == [("tile", (host, "p", 7), {}), ("rows", (host, ("p",)), {}),
                     ("reload", ("p",), {})]


def test_recipe_commit_pushes_an_edit_command(monkeypatch):
    built = []

    def _command(*args):
        built.append(args)
        return "cmd"

    monkeypatch.setattr(
        "Imervue.gpu_image_view.actions.recipe_commands.EditRecipeCommand", _command)
    pushed = []
    host = SimpleNamespace(undo_manager=SimpleNamespace(push=pushed.append))
    GPUImageView._on_recipe_committed(host, "p", "old", "new")
    assert built == [(host, "p", "old", "new")]
    assert pushed == ["cmd"]


# ---------------------------------------------------------------------------
# Modify panel / recipe reload / CVD
# ---------------------------------------------------------------------------

class _Panel:
    def __init__(self, visible=True):
        self.bound = []
        self.visible = visible

    def bind_to_path(self, path):
        self.bound.append(path)

    def isVisible(self):  # noqa: N802 - mirrors Qt's camelCase API
        return self.visible


class _Tabs:
    def __init__(self, count):
        self._count = count
        self.index = None

    def count(self):
        return self._count

    def setCurrentIndex(self, index):  # noqa: N802 - mirrors Qt's camelCase API
        self.index = index


def _panel_host(images, index, panel, tabs=None):
    main = SimpleNamespace(modify_panel=panel)
    if tabs is not None:
        main._main_tabs = tabs
    return SimpleNamespace(main_window=main, model=SimpleNamespace(images=images),
                           current_index=index,
                           _develop_panel=panel)


def test_develop_panel_property_reads_the_main_window():
    panel = _Panel()
    host = SimpleNamespace(main_window=SimpleNamespace(modify_panel=panel))
    assert GPUImageView._develop_panel.fget(host) is panel
    assert GPUImageView._develop_panel.fget(
        SimpleNamespace(main_window=SimpleNamespace())) is None


def test_open_develop_panel_without_panel_is_a_noop():
    host = _panel_host(["a"], 0, None)
    GPUImageView.open_develop_panel(host)


def test_open_develop_panel_binds_current_image_and_switches_tab():
    panel, tabs = _Panel(), _Tabs(3)
    GPUImageView.open_develop_panel(_panel_host(["a", "b"], 1, panel, tabs))
    assert panel.bound == ["b"]
    assert tabs.index == 1


@pytest.mark.parametrize("index", [-1, 2])
def test_open_develop_panel_out_of_range_binds_none(index):
    panel, tabs = _Panel(), _Tabs(1)
    GPUImageView.open_develop_panel(_panel_host(["a", "b"], index, panel, tabs))
    assert panel.bound == [None]
    assert tabs.index is None


def test_open_develop_panel_without_tabs_still_binds():
    panel = _Panel()
    GPUImageView.open_develop_panel(_panel_host([], 0, panel))
    assert panel.bound == [None]


def _reload_host(images, index, panel=None):
    calls = []
    host = SimpleNamespace(
        model=SimpleNamespace(images=images), current_index=index,
        _develop_panel=panel,
        _prefetch=SimpleNamespace(discard=_recorder(calls, "discard")),
        _save_view_state=_recorder(calls, "save"),
        _cancel_deep_zoom_worker=_recorder(calls, "cancel"),
        _clear_deep_zoom=_recorder(calls, "clear"),
        load_deep_zoom_image=_recorder(calls, "load"),
    )
    return host, calls


@pytest.mark.parametrize(("images", "index"), [([], 0), (["a"], 1)])
def test_reload_without_path_and_no_current_image_does_nothing(images, index):
    host, calls = _reload_host(images, index)
    GPUImageView.reload_current_image_with_recipe(host)
    assert calls == []


def test_reload_current_image_runs_teardown_then_load_and_rebinds_panel():
    panel = _Panel(visible=True)
    host, calls = _reload_host(["a", "b"], 1, panel)
    GPUImageView.reload_current_image_with_recipe(host)
    assert [c[0] for c in calls] == ["discard", "save", "cancel", "clear", "load"]
    assert calls[0][1] == ("b",)
    assert calls[-1][1] == ("b",)
    assert panel.bound == ["b"]


def test_reload_with_hidden_panel_does_not_rebind():
    panel = _Panel(visible=False)
    host, _calls = _reload_host(["a"], 0, panel)
    GPUImageView.reload_current_image_with_recipe(host, "a")
    assert panel.bound == []


def test_reload_of_a_non_current_path_only_drops_its_prefetch():
    host, calls = _reload_host(["a", "b"], 0)
    GPUImageView.reload_current_image_with_recipe(host, "b")
    assert calls == [("discard", ("b",), {})]


def test_set_cvd_view_mode_sets_mode_drops_prefetch_and_reloads(monkeypatch):
    calls = []
    monkeypatch.setattr("Imervue.gpu_image_view.cvd_view_mode.set_view_mode",
                        _recorder(calls, "mode"))
    host = SimpleNamespace(_cancel_all_prefetch=_recorder(calls, "cancel"),
                           reload_current_image_with_recipe=_recorder(calls, "reload"))
    GPUImageView.set_cvd_view_mode(host, "deutan")
    assert calls == [("mode", ("deutan",), {}), ("cancel", (), {}), ("reload", (), {})]


# ---------------------------------------------------------------------------
# Bookmark / toast / current path
# ---------------------------------------------------------------------------

def _lang_main(with_toast=True):
    toasts = []
    main = SimpleNamespace(language_wrapper=SimpleNamespace(language_word_dict={}))
    if with_toast:
        main.toast = SimpleNamespace(info=toasts.append)
    return main, toasts


@pytest.mark.parametrize(("marked", "expected_call", "message"), [
    (False, "add", "★ Bookmarked"),
    (True, "remove", "Bookmark removed"),
])
def test_toggle_bookmark_flips_state_and_toasts(monkeypatch, marked, expected_call,
                                                message):
    calls = []
    monkeypatch.setattr("Imervue.user_settings.bookmark.is_bookmarked",
                        lambda _p: marked)
    monkeypatch.setattr("Imervue.user_settings.bookmark.add_bookmark",
                        _recorder(calls, "add"))
    monkeypatch.setattr("Imervue.user_settings.bookmark.remove_bookmark",
                        _recorder(calls, "remove"))
    main, toasts = _lang_main()
    updates = []
    host = SimpleNamespace(main_window=main, model=SimpleNamespace(images=["a"]),
                           current_index=0, update=lambda: updates.append(1))
    GPUImageView._toggle_bookmark(host)
    assert calls == [(expected_call, ("a",), {})]
    assert toasts == [message]
    assert updates == [1]


def test_toggle_bookmark_without_toast_still_repaints(monkeypatch):
    monkeypatch.setattr("Imervue.user_settings.bookmark.is_bookmarked", lambda _p: False)
    monkeypatch.setattr("Imervue.user_settings.bookmark.add_bookmark", lambda _p: None)
    main, _toasts = _lang_main(with_toast=False)
    updates = []
    host = SimpleNamespace(main_window=main, model=SimpleNamespace(images=["a"]),
                           current_index=0, update=lambda: updates.append(1))
    GPUImageView._toggle_bookmark(host)
    assert updates == [1]


@pytest.mark.parametrize(("images", "index"), [([], 0), (["a"], 1)])
def test_toggle_bookmark_without_current_image_is_a_noop(images, index):
    host = SimpleNamespace(model=SimpleNamespace(images=images), current_index=index)
    GPUImageView._toggle_bookmark(host)


def test_toast_uses_the_translation_or_fallback():
    main, toasts = _lang_main()
    main.language_wrapper.language_word_dict["k"] = "translated"
    host = SimpleNamespace(main_window=main)
    GPUImageView._toast(host, "k", "fallback")
    GPUImageView._toast(host, "missing", "fallback")
    assert toasts == ["translated", "fallback"]
    GPUImageView._toast(SimpleNamespace(main_window=SimpleNamespace()), "k", "f")


@pytest.mark.parametrize(("images", "index", "expected"), [
    ([], 0, None), (["a", "b"], 1, "b"), (["a"], 1, None), (["a"], -1, None),
])
def test_current_path(images, index, expected):
    host = SimpleNamespace(model=SimpleNamespace(images=images), current_index=index)
    assert GPUImageView._current_path(host) == expected


# ---------------------------------------------------------------------------
# Thumbnail size / tile grid
# ---------------------------------------------------------------------------

def _size_host(images, deep_zoom, tile_grid_mode):
    calls = []
    host = SimpleNamespace(
        model=SimpleNamespace(images=images), deep_zoom=deep_zoom,
        tile_grid_mode=tile_grid_mode, _tile_size_dirty=False,
        thumbnail_size=None,
        clear_tile_grid=_recorder(calls, "clear"),
        load_tile_grid_async=_recorder(calls, "load"),
        update=_recorder(calls, "update"),
    )
    return host, calls


def test_thumbnail_size_on_the_wall_rebuilds_the_grid():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    host, calls = _size_host(["a"], None, True)
    GPUImageView.set_thumbnail_size(host, 256)
    assert host.thumbnail_size == 256
    assert user_setting_dict["thumbnail_size"] == 256
    assert calls == [("clear", (), {}), ("load", (), {"image_paths": ["a"]})]


def test_thumbnail_size_in_deep_zoom_defers_the_rebuild():
    host, calls = _size_host(["a"], object(), False)
    GPUImageView.set_thumbnail_size(host, 128)
    assert host._tile_size_dirty is True
    assert calls == [("update", (), {})]


def test_thumbnail_size_none_string_with_no_images_only_stores():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    host, calls = _size_host([], None, True)
    GPUImageView.set_thumbnail_size(host, "None")
    assert host.thumbnail_size is None
    assert user_setting_dict["thumbnail_size"] is None
    assert calls == []
    assert host._tile_size_dirty is False


def test_clear_tile_grid_resets_wall_state(monkeypatch):
    from Imervue.gpu_image_view.tile_focus import NO_FOCUS
    calls = []
    monkeypatch.setattr("Imervue.gpu_image_view.tile_loader.stop_offline_sweep",
                        _recorder(calls, "stop"))
    host = SimpleNamespace(
        tile_grid_mode=True, tile_rects=[1], tile_cache={"a": 1},
        grid_offset_x=5, grid_offset_y=6, focused_tile_index=3,
        focus_ring_visible=True, _filmstrip_thumb_cache={"a": 1},
        _filmstrip_pending={"a"}, _tile_load_times={"a": 1},
        _tile_file_signatures={"a": 1}, _tile_retry_counts={"a": 1},
        _cancel_tile_workers=_recorder(calls, "cancel"),
        _delete_all_tile_textures=_recorder(calls, "delete"),
        update=_recorder(calls, "update"),
    )
    GPUImageView.clear_tile_grid(host)
    assert [c[0] for c in calls] == ["stop", "cancel", "delete", "update"]
    assert host.tile_grid_mode is False
    assert host.tile_rects == []
    assert (host.grid_offset_x, host.grid_offset_y) == (0, 0)
    assert host.focused_tile_index == NO_FOCUS
    assert host.focus_ring_visible is False
    for name in ("tile_cache", "_filmstrip_thumb_cache", "_filmstrip_pending",
                 "_tile_load_times", "_tile_file_signatures", "_tile_retry_counts"):
        assert not getattr(host, name), name


@pytest.mark.parametrize("offset", [-500, 0, 10 ** 6])
def test_clamp_grid_scroll_matches_the_layout_helpers(offset):
    from Imervue.gpu_image_view.tile_layout import clamp_grid_offset, tile_grid_layout
    host = SimpleNamespace(
        _tile_renderer=SimpleNamespace(base_size=lambda: 128),
        width=lambda: 800, height=lambda: 600, devicePixelRatio=lambda: 1.0,
        tile_scale=1.0, tile_padding=8, grid_offset_y=offset,
        model=SimpleNamespace(images=["x"] * 50),
    )
    draw_scale, cell, cols = tile_grid_layout(800, 128, 1.0, 8, 1.0)
    expected = clamp_grid_offset(offset, 50, cols, cell, 128 * draw_scale, 600)
    GPUImageView._clamp_grid_scroll(host)
    assert host.grid_offset_y == expected


# ---------------------------------------------------------------------------
# Teardown: deep zoom, workers, animation, Modify menu
# ---------------------------------------------------------------------------

class _Action:
    def __init__(self, fail=False):
        self.visible = []
        self.fail = fail

    def setVisible(self, value):  # noqa: N802 - mirrors Qt's camelCase API
        if self.fail:
            raise RuntimeError("deleted")
        self.visible.append(value)


def test_modify_menu_toggle_tolerates_missing_and_failing_action(caplog):
    GPUImageView._set_modify_menu_visible(
        SimpleNamespace(main_window=SimpleNamespace()), True)
    action = _Action()
    GPUImageView._set_modify_menu_visible(
        SimpleNamespace(main_window=SimpleNamespace(_modify_menu_action=action)), 1)
    assert action.visible == [True]
    with caplog.at_level(logging.WARNING, logger="Imervue"):
        GPUImageView._set_modify_menu_visible(
            SimpleNamespace(main_window=SimpleNamespace(
                _modify_menu_action=_Action(fail=True))), False)
    assert "toggle the Modify menu" in caplog.text


def _deep_zoom_host(main_window, calls):
    host = SimpleNamespace(
        _deep_zoom_loading=object(), _deep_zoom_path="a",
        _stop_animation=_recorder(calls, "stop"),
        _current_gl_context=contextlib.nullcontext,
        tile_manager=SimpleNamespace(clear=_recorder(calls, "tm_clear")),
        _minimap_tex=42, _minimap_dzi=object(), deep_zoom=object(),
        _hover_image_xy=(1, 2), main_window=main_window,
    )
    return _bind(host, "_set_modify_menu_visible")


def test_clear_deep_zoom_frees_everything_and_hides_the_modify_menu(monkeypatch):
    calls = []
    owner = sys.modules[_owner("_clear_deep_zoom").__module__]
    monkeypatch.setattr(owner, "glDeleteTextures", _recorder(calls, "gl_delete"))
    action = _Action()
    main = SimpleNamespace(_modify_menu_action=action,
                           clear_status_info=_recorder(calls, "status"))
    host = _deep_zoom_host(main, calls)
    GPUImageView._clear_deep_zoom(host)
    assert [c[0] for c in calls] == ["stop", "tm_clear", "gl_delete", "status"]
    assert calls[2][1] == ([42],)
    assert host.tile_manager is None
    assert host._minimap_tex is None
    assert host._minimap_dzi is None
    assert host.deep_zoom is None
    assert host._deep_zoom_loading is None
    assert host._deep_zoom_path is None
    assert host._hover_image_xy is None
    assert action.visible == [False]


def test_clear_deep_zoom_with_nothing_loaded_and_failing_status_clear(monkeypatch, caplog):
    calls = []
    owner = sys.modules[_owner("_clear_deep_zoom").__module__]
    monkeypatch.setattr(owner, "glDeleteTextures", _recorder(calls, "gl_delete"))

    def _boom():
        raise RuntimeError("gone")

    host = _deep_zoom_host(SimpleNamespace(clear_status_info=_boom), calls)
    host.tile_manager = None
    host._minimap_tex = None
    with caplog.at_level(logging.WARNING, logger="Imervue"):
        GPUImageView._clear_deep_zoom(host)
    assert [c[0] for c in calls] == ["stop"]
    assert host.deep_zoom is None
    assert "clear the status bar info" in caplog.text


def test_clear_deep_zoom_without_status_slot():
    calls = []
    host = _deep_zoom_host(SimpleNamespace(), calls)
    host.tile_manager = None
    host._minimap_tex = None
    GPUImageView._clear_deep_zoom(host)
    assert host.deep_zoom is None


class _Signal:
    def __init__(self, log, label, error=None):
        self.log, self.label, self.error = log, label, error

    def disconnect(self):
        self.log.append(self.label)
        if self.error is not None:
            raise self.error


class _Worker:
    def __init__(self, log, name, *, finished_error=None, error_signal=True):
        signals = SimpleNamespace(
            finished=_Signal(log, f"{name}.finished", finished_error))
        if error_signal:
            signals.error = _Signal(log, f"{name}.error", TypeError("no slot"))
        self.signals = signals
        self.log, self.name = log, name

    def abort(self):
        self.log.append(f"{self.name}.abort")


def test_cancel_deep_zoom_worker_disconnects_and_aborts_both():
    log = []
    host = SimpleNamespace(
        active_deep_zoom_worker=_Worker(log, "dz", finished_error=RuntimeError("x")),
        active_deep_zoom_preview_worker=_Worker(log, "pv", error_signal=False),
    )
    GPUImageView._cancel_deep_zoom_worker(host)
    assert log == ["dz.finished", "dz.error", "dz.abort", "pv.finished", "pv.abort"]
    assert host.active_deep_zoom_worker is None
    assert host.active_deep_zoom_preview_worker is None


def test_cancel_deep_zoom_worker_with_nothing_running():
    host = SimpleNamespace(active_deep_zoom_worker=None,
                           active_deep_zoom_preview_worker=None)
    GPUImageView._cancel_deep_zoom_worker(host)
    assert host.active_deep_zoom_worker is None


def test_cancel_tile_workers_aborts_each_and_clears_queues():
    log = []
    pending = {"x"}
    host = SimpleNamespace(
        _tile_queue=object(), _filmstrip_pending=pending,
        active_tile_workers={_Worker(log, "t", error_signal=False)},
    )
    GPUImageView._cancel_tile_workers(host)
    assert log == ["t.finished", "t.abort"]
    assert host._tile_queue is None
    assert pending == set()
    assert host.active_tile_workers == set()
    GPUImageView._cancel_tile_workers(
        SimpleNamespace(_tile_queue=None, active_tile_workers=set()))


class _Player:
    instances: list[_Player] = []
    loads = True

    def __init__(self, view, path):
        self.view, self.path, self.log = view, path, []
        _Player.instances.append(self)

    def load(self):
        return _Player.loads

    def play(self):
        self.log.append("play")

    def stop(self):
        self.log.append("stop")


@pytest.mark.parametrize("loads", [True, False])
def test_init_animation_stops_the_old_player_and_plays_a_loaded_one(monkeypatch, loads):
    _Player.instances, _Player.loads = [], loads
    monkeypatch.setattr(
        "Imervue.gpu_image_view.actions.animation_player.AnimationPlayer", _Player)
    old = _Player(None, "old")
    _Player.instances = []
    host = _bind(SimpleNamespace(_animation=old), "_stop_animation")
    GPUImageView._init_animation(host, "a.gif")
    assert old.log == ["stop"]
    (player,) = _Player.instances
    assert (player.view, player.path) == (host, "a.gif")
    if loads:
        assert host._animation is player
        assert player.log == ["play"]
    else:
        assert host._animation is None
        assert player.log == []


def test_stop_animation_without_a_player_is_a_noop():
    host = SimpleNamespace(_animation=None)
    GPUImageView._stop_animation(host)
    assert host._animation is None


# ---------------------------------------------------------------------------
# Drag & drop
# ---------------------------------------------------------------------------

class _DragEvent:
    def __init__(self, has_urls):
        self._has = has_urls
        self.accepted = False

    def mimeData(self):  # noqa: N802 - mirrors Qt's camelCase API
        return SimpleNamespace(hasUrls=lambda: self._has)

    def acceptProposedAction(self):  # noqa: N802 - mirrors Qt's camelCase API
        self.accepted = True


@pytest.mark.parametrize("handler", ["dragEnterEvent", "dragMoveEvent"])
@pytest.mark.parametrize("has_urls", [True, False])
def test_drag_accepts_only_url_payloads(handler, has_urls):
    host = _bind(SimpleNamespace(), "_accept_url_drag")
    event = _DragEvent(has_urls)
    getattr(GPUImageView, handler)(host, event)
    assert event.accepted is has_urls


def test_drop_delegates_to_the_drop_handler(monkeypatch):
    calls = []
    monkeypatch.setattr("Imervue.gpu_image_view.drop_handler.handle_drop",
                        _recorder(calls, "drop"))
    host = SimpleNamespace()
    GPUImageView.dropEvent(host, "ev")
    assert calls == [("drop", (host, "ev"), {})]
