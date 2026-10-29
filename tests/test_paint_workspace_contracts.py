"""Contracts of the Paint workspace's drop, history, cursor, menu and navigator paths.

The methods are driven unbound on lightweight hosts (``SimpleNamespace`` or a
``PaintWorkspace`` subclass that only runs ``QMainWindow.__init__``), so no
``QOpenGLWidget`` is ever constructed and the module runs on headless CI.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import numpy as np
import pytest
import shiboken6
from PIL import Image
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QMainWindow, QTabBar, QWidget

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import tool_state as ts
from Imervue.paint.document import PaintDocument
from Imervue.paint.paint_workspace import PaintWorkspace, _pointer_button_held


class _Event:
    """Records accept / ignore on a fake drag or drop event."""

    def __init__(self, urls=None):
        self._urls = urls
        self.calls: list[str] = []

    def mimeData(self):  # noqa: N802 - Qt-shaped fake
        urls = self._urls
        return SimpleNamespace(hasUrls=lambda: urls is not None, urls=lambda: urls or [])

    def acceptProposedAction(self):  # noqa: N802 - Qt-shaped fake
        self.calls.append("accept")

    def ignore(self):
        self.calls.append("ignore")


def _drop_host(**extra):
    host = SimpleNamespace(
        SUPPORTED_DROP_EXTS=PaintWorkspace.SUPPORTED_DROP_EXTS,
        opened=[],
    )
    host._is_supported_drop = lambda path: PaintWorkspace._is_supported_drop(host, path)
    host._open_dropped_path = host.opened.append
    for key, value in extra.items():
        setattr(host, key, value)
    return host


# ---------------------------------------------------------------------------
# drag and drop
# ---------------------------------------------------------------------------


def test_supported_drop_extensions_cover_documents_psd_and_rasters():
    exts = PaintWorkspace.SUPPORTED_DROP_EXTS
    assert exts == tuple(sorted(exts))
    for ext in (".imervue", ".psd", ".png", ".tif", ".tiff", ".bmp", ".webp", ".jpg"):
        assert ext in exts


@pytest.mark.parametrize(("path", "expected"), [
    ("C:/a/B.PNG", True), ("x.imervue", True), ("x.Psd", True),
    ("x.gif", False), ("png", False), ("", False),
])
def test_is_supported_drop_matches_case_insensitively(path, expected):
    assert PaintWorkspace._is_supported_drop(_drop_host(), path) is expected


def test_drag_enter_without_urls_is_ignored():
    event = _Event(urls=None)
    PaintWorkspace.dragEnterEvent(_drop_host(), event)
    assert event.calls == ["ignore"]


def test_drag_enter_accepts_on_first_supported_local_file():
    urls = [QUrl("https://example.com/a.png"), QUrl.fromLocalFile("C:/x.txt"),
            QUrl.fromLocalFile("C:/y.png"), QUrl.fromLocalFile("C:/z.png")]
    event = _Event(urls=urls)
    PaintWorkspace.dragEnterEvent(_drop_host(), event)
    assert event.calls == ["accept"]


def test_drag_enter_with_only_unsupported_files_is_ignored():
    event = _Event(urls=[QUrl.fromLocalFile("C:/x.txt")])
    PaintWorkspace.dragEnterEvent(_drop_host(), event)
    assert event.calls == ["ignore"]


def test_drag_move_mirrors_drag_enter():
    seen: list = []
    host = SimpleNamespace(dragEnterEvent=seen.append)
    event = _Event(urls=[])
    PaintWorkspace.dragMoveEvent(host, event)
    assert seen == [event]


def test_drop_without_urls_is_ignored():
    host = _drop_host()
    event = _Event(urls=None)
    PaintWorkspace.dropEvent(host, event)
    assert event.calls == ["ignore"]
    assert host.opened == []


def test_drop_opens_every_supported_local_file_in_order():
    host = _drop_host()
    urls = [QUrl.fromLocalFile("C:/a.png"), QUrl("https://example.com/b.png"),
            QUrl.fromLocalFile("C:/c.txt"), QUrl.fromLocalFile("C:/d.psd")]
    event = _Event(urls=urls)
    PaintWorkspace.dropEvent(host, event)
    assert host.opened == ["C:/a.png", "C:/d.psd"]
    assert event.calls == ["accept"]


def test_drop_with_nothing_openable_is_ignored():
    host = _drop_host()
    event = _Event(urls=[QUrl.fromLocalFile("C:/c.txt")])
    PaintWorkspace.dropEvent(host, event)
    assert host.opened == []
    assert event.calls == ["ignore"]


def test_dropped_document_opens_through_the_bridge():
    opened: list = []
    host = SimpleNamespace(_file_menu_bridge=SimpleNamespace(open_document_at=opened.append))
    PaintWorkspace._open_dropped_path(host, "C:/Doc.IMERVUE")
    assert opened == ["C:/Doc.IMERVUE"]


def test_dropped_psd_opens_through_the_bridge():
    opened: list = []
    host = SimpleNamespace(_file_menu_bridge=SimpleNamespace(open_psd_at=opened.append))
    PaintWorkspace._open_dropped_path(host, "C:/art.psd")
    assert opened == ["C:/art.psd"]


def test_dropped_psd_without_bridge_falls_back_to_decode(caplog, tmp_path):
    host = SimpleNamespace(_file_menu_bridge=None)
    bad = tmp_path / "broken.psd"
    bad.write_bytes(b"not a psd")
    with caplog.at_level(logging.WARNING, logger="Imervue.paint.workspace"):
        PaintWorkspace._open_dropped_path(host, str(bad))
    assert any("could not be opened" in r.getMessage() for r in caplog.records)


def test_dropped_raster_on_dirty_tab_opens_a_new_tab_and_refreshes_recent(tmp_path):
    from Imervue.paint import recent_files
    path = tmp_path / "x.png"
    Image.fromarray(np.zeros((3, 5, 4), dtype=np.uint8), "RGBA").save(str(path))
    calls: list = []
    canvas = object()
    host = SimpleNamespace(
        _canvas=canvas, _tab_dirty={canvas: True},
        new_tab=lambda **kw: calls.append(("new_tab", kw)),
        load_image=lambda arr, *, source_path="": calls.append(("load", arr.shape, source_path)),
        _file_menu_bridge=SimpleNamespace(refresh_recent_menu=lambda: calls.append("refresh")),
    )
    PaintWorkspace._open_dropped_path(host, str(path))
    assert calls == [("new_tab", {"width": 1, "height": 1}),
                     ("load", (3, 5, 4), str(path)), "refresh"]
    assert recent_files.paths()[0] == str(path)


def test_unreadable_dropped_raster_logs_a_warning(caplog, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    loaded: list = []
    canvas = object()
    host = SimpleNamespace(_canvas=canvas, _tab_dirty={}, load_image=loaded.append,
                           _file_menu_bridge=None)
    with caplog.at_level(logging.WARNING, logger="Imervue.paint.workspace"):
        PaintWorkspace._open_dropped_path(host, str(bad))
    assert loaded == []
    assert any("could not be opened" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# undo / redo + history feedback
# ---------------------------------------------------------------------------


class _Stack:
    def __init__(self, ok=True):
        self.ok = ok
        self.commits: list = []
        self._undo = [1, 2]
        self._redo = [1]

    def commit(self, **kwargs):
        self.commits.append(kwargs)

    def undo(self):
        return self.ok

    def redo(self):
        return self.ok


def _history_host(stack, **extra):
    log: list = []
    host = SimpleNamespace(
        _pointer_stroke_active=lambda: False,
        _undo_stack=stack,
        _canvas=SimpleNamespace(invalidate_texture=lambda: log.append("tex"),
                                update=lambda: log.append("update")),
        _notify_history_action=lambda k: log.append(("action", k)),
        _notify_history_empty=lambda k: log.append(("empty", k)),
        _set_tab_dirty=lambda canvas, dirty: log.append(("dirty", dirty)),
        log=log,
    )
    for key, value in extra.items():
        setattr(host, key, value)
    return host


def test_pointer_button_held_reexported():
    assert _pointer_button_held(Qt.MouseButton.LeftButton) is True


def test_pointer_stroke_active_is_false_without_buttons(qapp):
    assert PaintWorkspace._pointer_stroke_active() is False


def test_redo_success_marks_dirty_and_refreshes():
    host = _history_host(_Stack(ok=True))
    PaintWorkspace.redo(host)
    assert host.log == [("dirty", True), "tex", "update", ("action", "redo")]


def test_redo_and_undo_with_empty_stack_report_empty():
    host = _history_host(_Stack(ok=False))
    PaintWorkspace.redo(host)
    PaintWorkspace.undo(host)
    assert host.log == [("empty", "redo"), ("empty", "undo")]


def test_redo_deferred_while_pointer_held():
    host = _history_host(_Stack(ok=True), _pointer_stroke_active=lambda: True)
    PaintWorkspace.redo(host)
    assert host.log == []


def test_dispatcher_commit_passes_regions_when_dispatcher_has_them():
    stack = _Stack()
    host = _history_host(stack, _dispatcher=SimpleNamespace(history_regions=["r"]))
    PaintWorkspace._on_dispatcher_commit(host)
    assert stack.commits == [{"regions": ["r"]}]
    assert host.log == [("dirty", True)]


def test_dispatcher_commit_without_dispatcher_commits_whole():
    stack = _Stack()
    host = _history_host(stack)
    PaintWorkspace._on_dispatcher_commit(host)
    assert stack.commits == [{}]


def test_history_depth_reads_each_side_and_tolerates_missing():
    host = SimpleNamespace(_undo_stack=_Stack())
    assert PaintWorkspace._history_depth_for(host, "undo") == 2
    assert PaintWorkspace._history_depth_for(host, "redo") == 1
    host = SimpleNamespace(_undo_stack=SimpleNamespace(_undo=None))
    assert PaintWorkspace._history_depth_for(host, "undo") == 0
    assert PaintWorkspace._history_depth_for(host, "redo") == 0


def test_broadcast_prefers_toast_level_then_status():
    shown: list = []
    status = SimpleNamespace(showMessage=lambda m, t: shown.append(("status", m, t)))
    toast = SimpleNamespace(info=lambda m: shown.append(("info", m)))
    host = SimpleNamespace(toast=toast, _status=status)
    PaintWorkspace._broadcast_history_msg(host, "hi", level="info")
    PaintWorkspace._broadcast_history_msg(host, "warn", level="warning")
    PaintWorkspace._broadcast_history_msg(SimpleNamespace(), "none", level="info")
    assert shown == [("info", "hi"), ("status", "warn", 2000)]


def test_notify_messages_format_verb_depth_and_kind(monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})
    sent: list = []
    host = SimpleNamespace(
        _history_depth_for=lambda kind: 3,
        _broadcast_history_msg=lambda msg, *, level: sent.append((msg, level)),
    )
    PaintWorkspace._notify_history_action(host, "undo")
    PaintWorkspace._notify_history_empty(host, "redo")
    assert sent == [("Undo (3 left)", "info"), ("Nothing to redo", "warning")]


def test_undo_stack_property_recreated_when_document_replaced():
    class _Canvas:
        def __init__(self):
            self.doc = PaintDocument()

        def document(self):
            return self.doc

    canvas = _Canvas()
    host = SimpleNamespace(_canvas=canvas, _undo_stacks={})
    first = PaintWorkspace._undo_stack.__get__(host, PaintWorkspace)
    assert PaintWorkspace._undo_stack.__get__(host, PaintWorkspace) is first
    canvas.doc = PaintDocument()
    second = PaintWorkspace._undo_stack.__get__(host, PaintWorkspace)
    assert second is not first
    assert second.document is canvas.doc


# ---------------------------------------------------------------------------
# cursor + tool-state events
# ---------------------------------------------------------------------------


def _cursor_host(tool):
    log: list = []
    host = SimpleNamespace(
        _BRUSH_RING_TOOLS=PaintWorkspace._BRUSH_RING_TOOLS,
        _state=SimpleNamespace(tool=tool, brush=SimpleNamespace(size=12)),
        _canvas=SimpleNamespace(
            zoom_factor=lambda: 2.0,
            set_brush_size_cursor=lambda size, zoom, *, kind: log.append(("ring", size, zoom, kind)),
            set_cursor_for_tool=lambda t: log.append(("cursor", t)),
        ),
        _refresh_status_line=lambda: log.append("status"),
        _refresh_zoom_indicator=lambda z: log.append(("zoom", z)),
        log=log,
    )
    host._refresh_cursor_for_tool = lambda: log.append("refresh_cursor")
    host._raise_dock_for_tool = lambda: log.append("raise")
    return host


def test_brush_ring_tools_set():
    expected = frozenset({
        "brush", "eraser", "smudge", "blur", "clone_stamp", "dodge", "burn", "sponge"})
    assert expected == PaintWorkspace._BRUSH_RING_TOOLS


def test_state_event_tool_refreshes_cursor_dock_and_status():
    host = _cursor_host("fill")
    PaintWorkspace._on_state_event(host, ts.EVENT_TOOL)
    assert host.log == ["refresh_cursor", "raise", "status"]


@pytest.mark.parametrize(("tool", "expected"), [
    ("brush", ["refresh_cursor", "status"]), ("fill", ["status"]),
])
def test_state_event_brush_refreshes_ring_only_for_ring_tools(tool, expected):
    host = _cursor_host(tool)
    PaintWorkspace._on_state_event(host, ts.EVENT_BRUSH)
    assert host.log == expected


def test_state_event_other_channel_is_ignored():
    host = _cursor_host("brush")
    PaintWorkspace._on_state_event(host, "something-else")
    assert host.log == []


def test_refresh_cursor_ring_vs_plain_cursor():
    host = _cursor_host("eraser")
    PaintWorkspace._refresh_cursor_for_tool(host)
    host._state.tool = "fill"
    PaintWorkspace._refresh_cursor_for_tool(host)
    assert host.log == [("ring", 12, 2.0, "eraser"), ("cursor", "fill")]


@pytest.mark.parametrize(("tool", "expected"), [
    ("brush", ["refresh_cursor", ("zoom", 1.5)]), ("text", [("zoom", 1.5)]),
])
def test_zoom_change_refreshes_ring_and_zoom_chip(tool, expected):
    host = _cursor_host(tool)
    PaintWorkspace._on_zoom_changed_refresh_cursor(host, 1.5)
    assert host.log == expected


@pytest.mark.parametrize(("tool", "dock"), [
    ("brush", "brush"), ("eraser", "brush"), ("text", "brush"),
    ("fill", "fill"), ("eyedropper", "color"), ("lasso", None),
])
def test_raise_dock_for_tool(tool, dock):
    raised: list = []
    docks = {name: SimpleNamespace(raise_=lambda n=name: raised.append(n))
             for name in ("brush", "fill", "color")}
    host = SimpleNamespace(_state=SimpleNamespace(tool=tool), _brush_dock=docks["brush"],
                           _fill_dock=docks["fill"], _color_dock=docks["color"])
    PaintWorkspace._raise_dock_for_tool(host)
    assert raised == ([] if dock is None else [dock])


@pytest.mark.parametrize(("xy", "expected"), [
    ((3.7, 4.2), (3, 4)), ((0, 0), (0, 0)), ((-1, 5), None), ((5, -1), None),
])
def test_hover_changed_caches_position(xy, expected):
    refreshed: list = []
    host = SimpleNamespace(_last_hover="old", _refresh_status_line=lambda: refreshed.append(1))
    PaintWorkspace._on_hover_changed(host, *xy)
    assert host._last_hover == expected
    assert refreshed == [1]


def test_image_loaded_shows_size_dismisses_hint_and_marks_clean(monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})
    log: list = []
    canvas = object()
    host = SimpleNamespace(
        _canvas=canvas,
        _status=SimpleNamespace(showMessage=lambda m, t: log.append((m, t))),
        _dismiss_welcome_hint=lambda: log.append("dismiss"),
        _set_tab_dirty=lambda c, d: log.append(("dirty", c is canvas, d)),
    )
    PaintWorkspace._on_image_loaded(host, 4, 3)
    assert log == [("Canvas: 4 × 3", 3000), "dismiss", ("dirty", True, False)]


# ---------------------------------------------------------------------------
# canvas context menu helpers
# ---------------------------------------------------------------------------


def _selection_host(document):
    updates: list = []
    return SimpleNamespace(
        _canvas=SimpleNamespace(document=lambda: document, update=lambda: updates.append(1)),
        updates=updates,
    )


def test_select_all_sets_full_mask():
    doc = PaintDocument()
    doc.load_image(np.zeros((2, 3, 4), dtype=np.uint8))
    host = _selection_host(doc)
    PaintWorkspace._select_all_canvas(host)
    assert doc.selection().shape == (2, 3)
    assert bool(doc.selection().all())
    assert host.updates == [1]
    assert PaintWorkspace._has_active_selection(host) is True
    PaintWorkspace._deselect_canvas(host)
    assert PaintWorkspace._has_active_selection(host) is False
    assert host.updates == [1, 1]


def test_selection_helpers_tolerate_documents_without_support():
    host = _selection_host(SimpleNamespace(shape=None))
    PaintWorkspace._select_all_canvas(host)
    PaintWorkspace._deselect_canvas(host)
    assert PaintWorkspace._has_active_selection(host) is False
    assert host.updates == []
    host = _selection_host(SimpleNamespace(shape=(2, 2)))
    PaintWorkspace._select_all_canvas(host)
    assert host.updates == []


def test_has_active_selection_false_for_empty_mask():
    doc = SimpleNamespace(selection=lambda: np.zeros((2, 2), dtype=bool))
    assert PaintWorkspace._has_active_selection(_selection_host(doc)) is False


# ---------------------------------------------------------------------------
# navigator preview
# ---------------------------------------------------------------------------


def _nav_host(composite, *, histogram=True, timer_active=False):
    log: list = []
    host = SimpleNamespace(
        _nav_dirty=True,
        _canvas=SimpleNamespace(document=lambda: SimpleNamespace(composite=lambda: composite)),
        _navigator_dock=SimpleNamespace(set_preview_image=lambda p: log.append(("preview", p))),
        _push_composite_to_secondary_views=lambda c: log.append(("push", c is composite)),
        _nav_timer=SimpleNamespace(isActive=lambda: timer_active,
                                   start=lambda: log.append("start")),
        _refresh_status_line=lambda: log.append("status"),
        _dismiss_welcome_hint=lambda: log.append("dismiss"),
        log=log,
    )
    if histogram:
        host._histogram_dock = SimpleNamespace(set_histogram=lambda h: log.append(("hist", h)))
    return host


def test_navigator_preview_with_no_composite_clears_both_docks():
    host = _nav_host(None)
    PaintWorkspace._refresh_navigator_preview(host)
    assert host._nav_dirty is False
    assert host.log[0] == ("preview", None)
    assert host.log[1][0] == "hist"
    assert len(host.log) == 2


def test_navigator_preview_without_histogram_dock(qapp):
    host = _nav_host(None, histogram=False)
    PaintWorkspace._refresh_navigator_preview(host)
    assert host.log == [("preview", None)]
    composite = np.zeros((2, 3, 4), dtype=np.uint8)
    host = _nav_host(composite, histogram=False)
    PaintWorkspace._refresh_navigator_preview(host)
    assert [entry[0] for entry in host.log] == ["preview", "push"]


def test_navigator_preview_builds_pixmap_histogram_and_pushes(qapp):
    composite = np.full((2, 3, 4), 255, dtype=np.uint8)
    host = _nav_host(composite)
    PaintWorkspace._refresh_navigator_preview(host)
    kinds = [entry[0] for entry in host.log]
    assert kinds == ["preview", "hist", "push"]
    pixmap = host.log[0][1]
    assert (pixmap.width(), pixmap.height()) == (3, 2)
    assert host._nav_buffer == composite.tobytes()
    assert host.log[2] == ("push", True)


@pytest.mark.parametrize(("active", "expected"), [
    (False, ["start", "status", "dismiss"]), (True, ["status", "dismiss"]),
])
def test_document_changed_marks_dirty_and_coalesces(active, expected):
    host = _nav_host(None, timer_active=active)
    host._nav_dirty = False
    PaintWorkspace._on_document_changed(host)
    assert host._nav_dirty is True
    assert host.log == expected


# ---------------------------------------------------------------------------
# Qt dispatch through a real (GL-free) PaintWorkspace instance
# ---------------------------------------------------------------------------


@pytest.fixture
def shell(qapp):
    class Shell(PaintWorkspace):
        def __init__(self):
            QMainWindow.__init__(self)
            self._canvas_tab_bar = QTabBar(self)
            for name in ("a", "b"):
                self._canvas_tab_bar.addTab(name)
            self._canvas_tab_bar.resize(200, 30)
            self._canvas = QWidget(self)
            self.closed: list = []
            self.opened: list = []

        def close_tab(self, index):
            self.closed.append(index)

        def _open_dropped_path(self, path):
            self.opened.append(path)

    window = Shell()
    yield window
    shiboken6.delete(window)


def _middle_release(pos, button=Qt.MouseButton.MiddleButton):
    return QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(pos), QPointF(pos),
                       button, button, Qt.KeyboardModifier.NoModifier)


def test_middle_click_on_tab_closes_it_and_is_consumed(shell):
    rect = shell._canvas_tab_bar.tabRect(1)
    event = _middle_release(rect.center())
    assert shell.eventFilter(shell._canvas_tab_bar, event) is True
    assert shell.closed == [1]


def test_tab_bar_events_that_are_not_middle_releases_pass_through(shell):
    rect = shell._canvas_tab_bar.tabRect(0)
    assert shell._handle_tab_bar_event(_middle_release(rect.center(),
                                                       Qt.MouseButton.LeftButton)) is False
    assert shell._handle_tab_bar_event(QEvent(QEvent.Type.User)) is False
    assert shell._handle_tab_bar_event(_middle_release(QPoint(-50, -50))) is False
    assert shell.eventFilter(shell._canvas_tab_bar, QEvent(QEvent.Type.User)) is False
    assert shell.closed == []


def test_canvas_resize_recentres_visible_welcome_hint(shell):
    placed: list = []
    shell._welcome_hint = SimpleNamespace(isVisible=lambda: True,
                                          position_centred=lambda w, h: placed.append((w, h)))
    shell._canvas.resize(40, 30)
    assert shell.eventFilter(shell._canvas, QEvent(QEvent.Type.Resize)) is False
    assert placed == [(40, 30)]
    shell._welcome_hint = SimpleNamespace(isVisible=lambda: False,
                                          position_centred=lambda w, h: placed.append((w, h)))
    shell.eventFilter(shell._canvas, QEvent(QEvent.Type.Resize))
    assert placed == [(40, 30)]


def test_qt_dispatches_drag_and_drop_to_the_workspace(shell, qapp):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("C:/x.png"), QUrl.fromLocalFile("C:/y.txt")])
    actions = Qt.DropAction.CopyAction
    enter = QDragEnterEvent(QPoint(1, 1), actions, mime, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
    enter.setAccepted(False)
    qapp.sendEvent(shell, enter)
    assert enter.isAccepted() is True
    drop = QDropEvent(QPointF(1, 1), actions, mime, Qt.MouseButton.LeftButton,
                      Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(shell, drop)
    assert shell.opened == ["C:/x.png"]
