"""Contracts for the main window's tab, navigation, drop and memory-pressure slots.

The real window is a GL widget no test builds, so each slot is bound to a plain
stand-in carrying only the attributes it touches. Collaborators are patched on
whichever module owns the slot's code, so these tests pin behaviour, not layout.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QMimeData, Qt, QUrl
from PySide6.QtGui import QKeyEvent

from Imervue.Imervue_main_window import ImervueMainWindow
from tests._toast_spy import ToastSpy


def _owner(method_name: str):
    """The module whose globals the window's *method_name* reads."""
    attr = getattr(ImervueMainWindow, method_name)
    return sys.modules[getattr(attr, "__func__", attr).__module__]


# ---------------------------------------------------------------------------
# memory pressure
# ---------------------------------------------------------------------------


class _MemWindow:
    _collect_memory_pressure = ImervueMainWindow._collect_memory_pressure
    _on_memory_pressure_clear = ImervueMainWindow._on_memory_pressure_clear


def test_memory_pressure_without_viewer_reports_zeros():
    assert _MemWindow()._collect_memory_pressure() == {"used_bytes": 0, "limit_bytes": 0}


def test_memory_pressure_reads_viewer_counters():
    window = _MemWindow()
    window.viewer = SimpleNamespace(
        _vram_usage=12.7, _vram_limit=100, tile_textures={1: 1, 2: 2},
        _prefetch_cache={"a": 1},
    )
    assert window._collect_memory_pressure() == {
        "used_bytes": 12, "limit_bytes": 100, "tile_count": 2, "prefetch_count": 1,
    }


def test_memory_pressure_defaults_missing_viewer_counters():
    window = _MemWindow()
    window.viewer = SimpleNamespace()
    assert window._collect_memory_pressure() == {
        "used_bytes": 0, "limit_bytes": 0, "tile_count": 0, "prefetch_count": 0,
    }


def test_memory_pressure_clear_without_viewer_is_noop():
    _MemWindow()._on_memory_pressure_clear()


def test_memory_pressure_clear_drops_every_cache_in_order():
    calls = []
    window = _MemWindow()
    cache = {"k": 1}
    window.viewer = SimpleNamespace(
        _cancel_all_prefetch=lambda: calls.append("prefetch"),
        _delete_all_tile_textures=lambda: calls.append("tiles"),
        tile_cache=cache,
    )
    window._on_memory_pressure_clear()
    assert calls == ["prefetch", "tiles"]
    assert cache == {}


def test_memory_pressure_clear_skips_non_callables_and_non_dict_cache():
    window = _MemWindow()
    cache = ["kept"]
    window.viewer = SimpleNamespace(
        _cancel_all_prefetch=None, _delete_all_tile_textures="x", tile_cache=cache,
    )
    window._on_memory_pressure_clear()
    assert cache == ["kept"]


# ---------------------------------------------------------------------------
# main tab switching
# ---------------------------------------------------------------------------


class _Shortcut:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, flag):  # noqa: N802 - Qt naming
        self.enabled = flag


class _TabWindow:
    _on_main_tab_changed = ImervueMainWindow._on_main_tab_changed

    def __init__(self, images, index):
        self.log = []
        self.viewer = SimpleNamespace(model=SimpleNamespace(images=images), current_index=index)
        self._folder_tab_shortcuts = [_Shortcut(), _Shortcut()]
        self._build_optional_tab_on_open = lambda idx: self.log.append(("build", idx))
        self.modify_panel = SimpleNamespace(bind_to_path=lambda p: self.log.append(("bind", p)))
        self.exif_sidebar = SimpleNamespace(update_info=lambda: self.log.append("exif"))

    @property
    def paint_workspace(self):
        self.log.append("paint")
        return object()


@pytest.mark.parametrize("idx", [0, 1, 2, 3])
def test_folder_tab_shortcuts_only_live_on_the_browse_tab(idx):
    window = _TabWindow(["a.png"], 0)
    window._on_main_tab_changed(idx)
    assert [s.enabled for s in window._folder_tab_shortcuts] == [idx == 0] * 2
    assert window.log[0] == ("build", idx)


def test_modify_tab_binds_the_current_image():
    window = _TabWindow(["a.png", "b.png"], 1)
    window._on_main_tab_changed(1)
    assert window.log[1:] == [("bind", "b.png")]


@pytest.mark.parametrize(("images", "index"), [([], 0), (["a.png"], 1), (["a.png"], -1)])
def test_modify_tab_binds_none_without_a_current_image(images, index):
    window = _TabWindow(images, index)
    window._on_main_tab_changed(1)
    assert window.log[1:] == [("bind", None)]


def test_paint_tab_only_touches_the_workspace():
    window = _TabWindow(["a.png"], 0)
    window._on_main_tab_changed(2)
    assert window.log[1:] == ["paint"]


@pytest.mark.parametrize("idx", [0, 3])
def test_other_tabs_refresh_the_exif_sidebar(idx):
    window = _TabWindow(["a.png"], 0)
    window._on_main_tab_changed(idx)
    assert window.log[1:] == ["exif"]


# ---------------------------------------------------------------------------
# eventFilter routing
# ---------------------------------------------------------------------------


class _FilterBase:
    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        self.log.append("super")
        return "super-result"


def _filter_window(current_tab):
    fn = ImervueMainWindow.eventFilter
    rebound = types.FunctionType(fn.__code__, fn.__globals__, fn.__name__, fn.__defaults__,
                                 (types.CellType(_FilterWindow),))

    window = _FilterWindow()
    window.log = []
    window._workspace_tab_bar = object()
    window._main_tabs = SimpleNamespace(currentIndex=lambda: current_tab)
    window.modify_panel = SimpleNamespace(navigate_image=lambda d: window.log.append(("modify", d)))
    window._navigate_paint_image = lambda d: window.log.append(("paint", d))
    return window, rebound


class _FilterWindow(_FilterBase):
    pass


def _key(key):
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


@pytest.mark.parametrize(("tab", "key", "expected"), [
    (1, Qt.Key.Key_Left, ("modify", -1)),
    (1, Qt.Key.Key_Right, ("modify", 1)),
    (2, Qt.Key.Key_Left, ("paint", -1)),
    (2, Qt.Key.Key_Right, ("paint", 1)),
])
def test_arrow_keys_on_workspace_tab_bar_page_images(qapp, tab, key, expected):
    window, filt = _filter_window(tab)
    assert filt(window, window._workspace_tab_bar, _key(key)) is True
    assert window.log == [expected]


@pytest.mark.parametrize(("tab", "key"), [
    (0, Qt.Key.Key_Left), (1, Qt.Key.Key_Up), (2, Qt.Key.Key_A),
])
def test_other_keys_fall_through_to_qt(qapp, tab, key):
    window, filt = _filter_window(tab)
    assert filt(window, window._workspace_tab_bar, _key(key)) == "super-result"
    assert window.log == ["super"]


def test_keys_on_other_objects_and_non_key_events_fall_through(qapp):
    window, filt = _filter_window(1)
    assert filt(window, object(), _key(Qt.Key.Key_Left)) == "super-result"
    assert filt(window, window._workspace_tab_bar, QEvent(QEvent.Type.User)) == "super-result"
    assert window.log == ["super", "super"]


# ---------------------------------------------------------------------------
# folder / file navigation
# ---------------------------------------------------------------------------


class _Index:
    def __init__(self, path, valid=True):
        self.path, self._valid = path, valid

    def isValid(self):  # noqa: N802 - Qt naming
        return self._valid


class _NavWindow:
    on_file_clicked = ImervueMainWindow.on_file_clicked
    navigate_to_path = ImervueMainWindow.navigate_to_path
    _on_directory_loaded = ImervueMainWindow._on_directory_loaded
    _open_startup_folder = ImervueMainWindow._open_startup_folder

    def __init__(self, *, breadcrumb=True, valid_index=True):
        self.log = []
        log = self.log
        self.model = SimpleNamespace(
            setRootPath=lambda p: log.append(("root", p)),
            index=lambda p: _Index(p, valid_index),
            filePath=lambda idx: idx.path,
        )
        self.tree = SimpleNamespace(
            setRootIndex=lambda idx: log.append(("tree_root", idx.path)),
            update=lambda idx: log.append(("tree_update", idx.path)),
        )
        self.viewer = SimpleNamespace(
            clear_tile_grid=lambda: log.append("clear"),
            model=SimpleNamespace(images=["m.png"]),
        )
        self._image_metadata_index = SimpleNamespace(
            prime=lambda imgs, limit: log.append(("prime", list(imgs), limit)),
        )
        self._folder_view_sessions = {}
        self.filename_label = SimpleNamespace(setText=lambda t: log.append(("label", t)))
        if breadcrumb:
            self.breadcrumb = SimpleNamespace(set_path=lambda p: log.append(("crumb", p)))

    def _save_current_folder_session(self):
        self.log.append("save_session")

    def _refresh_tag_filter_options(self):
        self.log.append("tags")

    def _restore_folder_session(self, path):
        self.log.append(("restore", path))

    def _restore_deep_zoom_if_saved(self, session):
        self.log.append(("deep_zoom", session))

    def watch_folder(self, path):
        self.log.append(("watch", path))


@pytest.fixture
def nav(monkeypatch):
    log = []
    for name in ("navigate_to_path", "_open_startup_folder"):
        module = _owner(name)
        monkeypatch.setattr(module, "open_path",
                            lambda *, main_gui, path: main_gui.log.append(("open", path)))
        monkeypatch.setattr(module.language_wrapper, "language_word_dict",
                            {"main_window_current_folder_format": "Folder: {path}"})
    monkeypatch.setattr(_owner("navigate_to_path"), "rebuild_recent_menu",
                        lambda win: win.log.append("recent"))
    return log


def _attach(window):
    window.viewer.log = window.log
    return window


def test_navigate_to_folder_runs_the_full_sequence(nav, tmp_path):
    window = _attach(_NavWindow())
    window.navigate_to_path(str(tmp_path))
    p = str(tmp_path)
    assert window.log == [
        "save_session", ("root", p), ("tree_root", p), "clear", ("open", p),
        ("prime", ["m.png"], 512), "tags", ("restore", p), ("label", f"Folder: {p}"),
        ("crumb", p), ("watch", p), "recent",
    ]


def test_navigate_to_folder_primes_unfiltered_images_when_present(nav, tmp_path):
    window = _attach(_NavWindow())
    window.viewer._unfiltered_images = ["u1.png", "u2.png"]
    window.navigate_to_path(str(tmp_path))
    assert ("prime", ["u1.png", "u2.png"], 512) in window.log


def test_navigate_to_file_opens_it_and_points_the_breadcrumb_at_its_folder(nav, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"")
    window = _attach(_NavWindow())
    window.navigate_to_path(str(img))
    assert window.log == [
        "save_session", "clear", ("open", str(img)), ("crumb", str(tmp_path)), "recent",
    ]


def test_navigate_to_missing_path_only_rebuilds_recent(nav, tmp_path):
    window = _attach(_NavWindow())
    window.navigate_to_path(str(tmp_path / "ghost"))
    assert window.log == ["recent"]


def test_file_click_navigates_to_the_model_path(nav, tmp_path):
    window = _attach(_NavWindow())
    window.on_file_clicked(_Index(str(tmp_path / "ghost")))
    assert window.log == ["recent"]


@pytest.mark.parametrize("valid", [True, False])
def test_directory_loaded_updates_tree_only_for_valid_index(valid):
    window = _NavWindow(valid_index=valid)
    window._on_directory_loaded("D:/x")
    assert window.log == ([("tree_update", "D:/x")] if valid else [])


@pytest.mark.parametrize("breadcrumb", [True, False])
def test_open_startup_folder_restores_deep_zoom_session(nav, breadcrumb):
    window = _attach(_NavWindow(breadcrumb=breadcrumb))
    window._folder_view_sessions = {"F": {"deep": 1}}
    window._open_startup_folder("F")
    expected = [
        ("root", "F"), ("tree_root", "F"), ("open", "F"), ("prime", ["m.png"], 512),
        "tags", ("restore", "F"), ("deep_zoom", {"deep": 1}), ("label", "Folder: F"),
    ]
    if breadcrumb:
        expected.append(("crumb", "F"))
    expected.append(("watch", "F"))
    assert window.log == expected


def test_open_startup_folder_without_session_passes_empty_dict(nav):
    window = _attach(_NavWindow())
    window._open_startup_folder("G")
    assert ("deep_zoom", {}) in window.log


# ---------------------------------------------------------------------------
# drag and drop events
# ---------------------------------------------------------------------------


class _DropEvent:
    def __init__(self, urls, *, has_mime=True):
        self._mime = None
        if has_mime:
            self._mime = QMimeData()
            self._mime.setUrls(urls)
        self.result = None

    def mimeData(self):  # noqa: N802 - Qt naming
        return self._mime

    def acceptProposedAction(self):  # noqa: N802 - Qt naming
        self.result = "accepted"

    def ignore(self):
        self.result = "ignored"


class _DropWindow:
    _is_supported_drop = ImervueMainWindow._is_supported_drop
    dragEnterEvent = ImervueMainWindow.dragEnterEvent  # noqa: N815 - Qt naming
    dropEvent = ImervueMainWindow.dropEvent  # noqa: N815 - Qt naming

    def __init__(self):
        self.opened = []

    def _open_dropped_path(self, path):
        self.opened.append(path)


def _files(tmp_path: Path):
    img = tmp_path / "a.png"
    img.write_bytes(b"")
    txt = tmp_path / "a.txt"
    txt.write_bytes(b"")
    return img, txt


def test_drag_enter_accepts_when_any_local_url_is_supported(qapp, tmp_path):
    img, txt = _files(tmp_path)
    event = _DropEvent([QUrl.fromLocalFile(str(txt)), QUrl.fromLocalFile(str(img))])
    _DropWindow().dragEnterEvent(event)
    assert event.result == "accepted"


@pytest.mark.parametrize("kind", ["unsupported", "remote", "empty", "no_mime"])
def test_drag_enter_ignores_unsupported_payloads(qapp, tmp_path, kind):
    img, txt = _files(tmp_path)
    urls = {"unsupported": [QUrl.fromLocalFile(str(txt))],
            "remote": [QUrl("https://example.com/a.png")], "empty": [], "no_mime": []}[kind]
    event = _DropEvent(urls, has_mime=kind != "no_mime")
    _DropWindow().dragEnterEvent(event)
    assert event.result == "ignored"


def test_drop_opens_only_the_first_supported_local_path(qapp, tmp_path):
    img, txt = _files(tmp_path)
    window = _DropWindow()
    event = _DropEvent([QUrl("https://example.com/a.png"), QUrl.fromLocalFile(str(txt)),
                        QUrl.fromLocalFile(str(img)), QUrl.fromLocalFile(str(tmp_path))])
    window.dropEvent(event)
    assert [Path(p) for p in window.opened] == [img]
    assert event.result == "accepted"


@pytest.mark.parametrize("has_mime", [True, False])
def test_drop_without_supported_paths_is_ignored(qapp, tmp_path, has_mime):
    _img, txt = _files(tmp_path)
    window = _DropWindow()
    event = _DropEvent([QUrl.fromLocalFile(str(txt))], has_mime=has_mime)
    window.dropEvent(event)
    assert window.opened == []
    assert event.result == "ignored"


def test_dropped_file_failure_without_toast_only_logs(qapp, tmp_path, monkeypatch):
    img, _txt = _files(tmp_path)

    def boom(**_kwargs):
        raise RuntimeError("decoder boom")

    monkeypatch.setattr(_owner("_open_dropped_path"), "open_path", boom)
    window = SimpleNamespace(viewer=object())
    ImervueMainWindow._open_dropped_path(window, str(img))


def test_dropped_file_failure_toast_names_the_file(qapp, tmp_path, monkeypatch):
    img, _txt = _files(tmp_path)

    def boom(**_kwargs):
        raise RuntimeError("decoder boom")

    monkeypatch.setattr(_owner("_open_dropped_path"), "open_path", boom)
    window = SimpleNamespace(viewer=object(), toast=ToastSpy())
    ImervueMainWindow._open_dropped_path(window, str(img))
    assert window.toast.calls[0][0] == "error"
    assert "a.png" in window.toast.calls[0][1]
