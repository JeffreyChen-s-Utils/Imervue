"""Observable context action contracts shared by baseline and refactor."""

from types import SimpleNamespace
import importlib

import pytest
from PySide6.QtWidgets import QMenu

from Imervue.menu import right_click_menu as menu_api


@pytest.mark.parametrize(
    "images,zoom,index,error,expected",
    [
        ([], True, 0, ("bad", "error"), None),
        (["a", "b"], False, 0, ("bad", "error"), "bad"),
        (["a", "b"], True, 1, None, "b"),
        (["a"], True, -1, None, None),
        (["a"], False, 0, None, None),
    ],
)
def test_current_path_policy(images, zoom, index, error, expected):
    view = SimpleNamespace(
        model=SimpleNamespace(images=images),
        deep_zoom=zoom,
        current_index=index,
        _deep_zoom_error=error,
    )
    assert menu_api._current_image_path(view) == expected


@pytest.mark.parametrize(
    "name,module,function,refresh",
    [
        ("_tag_by_location", "Imervue.image.geo_keywords", "tag_paths_by_location", False),
        ("_index_keywords", "Imervue.library.keyword_index", "import_keywords_to_index", False),
        ("_auto_cull_blurry", "Imervue.library.auto_cull", "auto_cull_blurry", True),
        ("_auto_cull_low_quality", "Imervue.library.quality_cull", "auto_cull_low_quality", True),
    ],
)
@pytest.mark.parametrize("count,has_toast", [(0, True), (2, True), (2, False)])
def test_batch_operation_order(monkeypatch, name, module, function, refresh, count, has_toast):
    trace = []

    def operation(paths):
        trace.append(("operation", paths))
        return count

    monkeypatch.setattr(importlib.import_module(module), function, operation)
    window = SimpleNamespace()
    if has_toast:
        window.toast = SimpleNamespace(
            success=lambda text: trace.append(("success", text)),
            info=lambda text: trace.append(("info", text)),
        )
    view = SimpleNamespace(
        main_window=window, selected_tiles=["b", "a"], update=lambda: trace.append(("update",))
    )
    getattr(menu_api, name)(view)
    assert trace[0] == ("operation", ["b", "a"])
    offset = 1
    if refresh:
        assert trace[1] == ("update",)
        offset += 1
    if has_toast:
        assert trace[offset][0] == ("success" if count else "info")
        assert bool(trace[offset][1])
        offset += 1
    assert len(trace) == offset


def test_reveal_captures_path_when_built(qapp, monkeypatch):
    calls = []
    monkeypatch.setitem(
        menu_api._show_in_explorer_action.__globals__, "reveal_or_warn", calls.append
    )
    view = SimpleNamespace(
        model=SimpleNamespace(images=["a", "b"]), deep_zoom=True, current_index=0
    )
    menu = QMenu()
    try:
        menu_api._show_in_explorer_action(view, menu)
        view.current_index = 1
        menu.actions()[0].trigger()
        assert calls == ["a"]
    finally:
        menu.deleteLater()


def test_relocation_without_matching_index_still_loads(qapp, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: ("new", ""))
    loaded = []
    view = SimpleNamespace(
        model=SimpleNamespace(images=["a"]),
        current_index=8,
        offline_paths={"old"},
        tile_errors={"old": "error"},
        _deep_zoom_error=("old", "error"),
        load_deep_zoom_image=loaded.append,
    )
    menu_api._relocate_missing(view, "old")
    assert view.model.images == ["a"]
    assert view.current_index == 8
    assert view.offline_paths == set()
    assert view.tile_errors == {}
    assert view._deep_zoom_error is None
    assert loaded == ["new"]


def test_batch_rotation_reads_selection_when_triggered(qapp, monkeypatch):
    calls = []
    namespace = menu_api._batch_actions.__globals__
    monkeypatch.setitem(
        namespace, "batch_rotate", lambda gui, paths, angle: calls.append((paths, angle))
    )
    monkeypatch.setitem(namespace, "build_batch_tag_album_submenu", lambda *args: None)
    view = SimpleNamespace(tile_grid_mode=True, tile_selection_mode=True, selected_tiles=["a"])
    menu = QMenu()
    try:
        menu_api._batch_actions(view, menu)
        view.selected_tiles = ["b", "c"]
        menu.actions()[0].menu().actions()[2].trigger()
        assert calls == [(["b", "c"], 90)]
    finally:
        menu.deleteLater()


def test_retry_deep_zoom_wins_over_same_path_thumbnail(monkeypatch):
    loaded = []
    view = SimpleNamespace(
        _deep_zoom_error=("a", "error"),
        tile_errors={"a": "error"},
        load_deep_zoom_image=loaded.append,
    )
    menu_api._retry_load(view, "a")
    assert loaded == ["a"]
    assert view._deep_zoom_error is None
    assert view.tile_errors == {"a": "error"}


def test_delete_gates_do_not_require_nonempty_selection(qapp, monkeypatch):
    calls = []
    namespace = menu_api._delete_action.__globals__
    monkeypatch.setitem(namespace, "delete_selected_tiles", lambda gui: calls.append("selected"))
    monkeypatch.setitem(namespace, "delete_current_image", lambda gui: calls.append("current"))
    view = SimpleNamespace(
        tile_grid_mode=True, tile_selection_mode=True, selected_tiles=[], deep_zoom=True
    )
    menu = QMenu()
    try:
        menu_api._delete_action(view, menu)
        assert len(menu.actions()) == 2
        for action in menu.actions():
            action.trigger()
        assert calls == ["selected", "current"]
    finally:
        menu.deleteLater()
