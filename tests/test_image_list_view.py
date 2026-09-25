"""Tests for ImageListModel / ImageListView."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt


@pytest.fixture
def list_mod(qapp):
    from Imervue.gui.image_list_view import ImageListModel, ImageListView
    return ImageListModel, ImageListView


class TestImageListModel:
    def test_empty_model_has_zero_rows(self, list_mod):
        model_cls, _ = list_mod
        m = model_cls()
        assert m.rowCount() == 0
        assert m.columnCount() == model_cls.COL_COUNT

    def test_set_paths_resets(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        m = model_cls()
        a = str(tmp_path / "a.png")
        b = str(tmp_path / "b.png")
        m.set_paths([a, b])
        assert m.rowCount() == 2
        assert m.path_at(0) == a
        assert m.path_at(1) == b

    def test_name_display_uses_basename(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        path = str(tmp_path / "sub" / "pic.jpg")
        Path(path).parent.mkdir()
        Path(path).write_bytes(b"fake")
        m = model_cls([path])
        idx = m.index(0, model_cls.COL_NAME)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "pic.jpg"

    def test_type_display_is_upper_extension(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        m = model_cls([str(tmp_path / "pic.PnG")])
        idx = m.index(0, model_cls.COL_TYPE)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "PNG"

    def test_sort_by_name(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        m = model_cls([
            str(tmp_path / "charlie.png"),
            str(tmp_path / "alpha.png"),
            str(tmp_path / "beta.png"),
        ])
        m.sort(model_cls.COL_NAME, Qt.SortOrder.AscendingOrder)
        names = [Path(m.path_at(i)).name for i in range(m.rowCount())]
        assert names == ["alpha.png", "beta.png", "charlie.png"]

    def test_user_role_returns_path(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        p = str(tmp_path / "x.png")
        m = model_cls([p])
        idx = m.index(0, 0)
        assert m.data(idx, Qt.ItemDataRole.UserRole) == p

    def test_missing_path_is_marked_in_name_column(self, list_mod, tmp_path):
        model_cls, _ = list_mod
        p = str(tmp_path / "gone.png")
        m = model_cls([p])
        idx = m.index(0, model_cls.COL_NAME)
        assert "gone.png" in m.data(idx, Qt.ItemDataRole.DisplayRole)
        assert "Missing" in m.data(idx, Qt.ItemDataRole.DisplayRole)
        assert m.is_missing_at(0) is True

    def test_rating_display_is_empty_when_unrated(self, list_mod, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        model_cls, _ = list_mod
        p = str(tmp_path / "unrated.png")
        user_setting_dict.pop("image_ratings", None)
        m = model_cls([p])
        idx = m.index(0, model_cls.COL_RATING)
        assert m.data(idx, Qt.ItemDataRole.DisplayRole) == ""

    def test_rating_display_uses_filled_and_empty_stars(self, list_mod, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        model_cls, _ = list_mod
        p = str(tmp_path / "rated.png")
        user_setting_dict["image_ratings"] = {p: 3}
        try:
            m = model_cls([p])
            idx = m.index(0, model_cls.COL_RATING)
            value = m.data(idx, Qt.ItemDataRole.DisplayRole)
            assert value == "\u2605\u2605\u2605\u2606\u2606"
        finally:
            user_setting_dict.pop("image_ratings", None)

    def test_sort_by_rating_is_numeric(self, list_mod, tmp_path):
        from Imervue.user_settings.user_setting_dict import user_setting_dict
        model_cls, _ = list_mod
        low = str(tmp_path / "low.png")
        mid = str(tmp_path / "mid.png")
        high = str(tmp_path / "high.png")
        user_setting_dict["image_ratings"] = {low: 1, mid: 3, high: 5}
        try:
            m = model_cls([mid, low, high])
            m.sort(model_cls.COL_RATING, Qt.SortOrder.DescendingOrder)
            order = [Path(m.path_at(i)).name for i in range(m.rowCount())]
            assert order == ["high.png", "mid.png", "low.png"]
        finally:
            user_setting_dict.pop("image_ratings", None)

    def test_sort_remaps_persistent_indexes(self, list_mod, tmp_path):
        """A header sort must carry selection / current (persistent indexes)
        with the rows they point at, not leave them mapped to the old row."""
        from PySide6.QtCore import QPersistentModelIndex
        model_cls, _ = list_mod
        z = str(tmp_path / "z.png")
        a = str(tmp_path / "a.png")
        m = model_cls([z, a])                       # rows: [z, a]
        tracked = QPersistentModelIndex(m.index(0, model_cls.COL_NAME))
        assert m.path_at(tracked.row()) == z

        m.sort(model_cls.COL_NAME, Qt.SortOrder.AscendingOrder)   # rows: [a, z]

        assert m.path_at(1) == z
        assert tracked.row() == 1                   # persistent index followed z
        assert m.path_at(tracked.row()) == z

    def test_pixmap_from_image_null_yields_placeholder(self, list_mod):
        from PySide6.QtGui import QImage
        model_cls, _ = list_mod
        placeholder = model_cls._pixmap_from_image(QImage())  # noqa: SLF001
        assert not placeholder.isNull()             # dark placeholder, not empty
        real = model_cls._pixmap_from_image(          # noqa: SLF001
            QImage(10, 10, QImage.Format.Format_RGBA8888))
        assert (real.width(), real.height()) == (10, 10)


class TestImageListViewBasics:
    def test_view_builds_with_empty_model(self, list_mod, qapp):
        _, view_cls = list_mod
        # MainWindow mock: only tolerates attribute access
        from unittest.mock import MagicMock
        v = view_cls(MagicMock())
        assert v.selected_paths() == []


# ---------------------------------------------------------------------------
# Phase 21 — empty-state hint when the model carries no rows.
# ---------------------------------------------------------------------------


def test_empty_state_hint_renders_when_no_paths(qapp):
    """The view paints a centred message when there are no images
    so users opening an empty folder don't stare at a blank table."""
    from Imervue.gui.image_list_view import ImageListView
    view = ImageListView(main_window=None)
    try:
        view.set_paths([])
        assert view._model.rowCount() == 0  # noqa: SLF001
        # The paint-event branch can be exercised by triggering a
        # repaint into a QImage — verifying it doesn't crash on the
        # empty path is the contract.
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QImage, QPaintEvent
        view.resize(200, 80)
        img = QImage(view.size(), QImage.Format.Format_RGB32)
        img.fill(0)
        evt = QPaintEvent(QRect(0, 0, 200, 80))
        view.paintEvent(evt)
    finally:
        view.deleteLater()


def test_empty_state_hint_skipped_with_paths(qapp, tmp_path):
    """A populated model never enters the hint branch — the table
    paints rows normally."""
    from PIL import Image as PILImage
    from Imervue.gui.image_list_view import ImageListView
    img_path = tmp_path / "x.png"
    PILImage.new("RGB", (4, 4)).save(img_path)
    view = ImageListView(main_window=None)
    try:
        view.set_paths([str(img_path)])
        assert view._model.rowCount() == 1  # noqa: SLF001
    finally:
        view.deleteLater()


def test_ctrl_c_copies_selected_paths_to_clipboard(qapp, tmp_path, fake_clipboard):
    """Ctrl+C on a selection writes the file paths to the system
    clipboard so the user can paste them elsewhere — common QoL
    in file browsers."""
    from PIL import Image as PILImage
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from Imervue.gui.image_list_view import ImageListView

    images = []
    for name in ("a.png", "b.png"):
        p = tmp_path / name
        PILImage.new("RGB", (4, 4)).save(p)
        images.append(str(p))
    view = ImageListView(main_window=None)
    try:
        view.set_paths(images)
        view.selectAll()
        evt = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_C,
            Qt.KeyboardModifier.ControlModifier,
        )
        view.keyPressEvent(evt)
        clipboard = QApplication.clipboard().text()
        assert "a.png" in clipboard
        assert "b.png" in clipboard
    finally:
        view.deleteLater()


def test_context_menu_no_op_on_empty_selection(qapp):
    """Right-clicking with nothing selected mustn't raise — the
    handler returns early so the menu never appears."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QContextMenuEvent
    from Imervue.gui.image_list_view import ImageListView
    view = ImageListView(main_window=None)
    try:
        view.set_paths([])
        evt = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse,
            QPoint(10, 10),
            QPoint(10, 10),
        )
        view.contextMenuEvent(evt)
    finally:
        view.deleteLater()


def test_reveal_in_folder_selects_the_photo(qapp, tmp_path, monkeypatch):
    """Reveal used to open the folder with nothing selected; Show in Explorer elsewhere selects.

    The file manager is stubbed so the test never opens a real window.
    """
    from Imervue.gui import image_list_view
    revealed: list = []
    monkeypatch.setattr(image_list_view, "reveal_or_warn", revealed.append)
    view = image_list_view.ImageListView(main_window=None)
    try:
        view._reveal_path(str(tmp_path / "a.png"))  # noqa: SLF001
    finally:
        view.deleteLater()
    assert revealed == [str(tmp_path / "a.png")]


class TestThumbFetchRetry:
    """A transient stat/decode failure must retry, not blank the row forever."""

    @staticmethod
    def _model(model_cls, path, monkeypatch):
        m = model_cls([path])
        started: list = []
        monkeypatch.setattr(m._pool, "start", started.append)  # noqa: SLF001
        return m, started

    @staticmethod
    def _image():
        # The worker now hands the model a QImage (QPixmap is GUI-thread-only).
        from PySide6.QtGui import QImage
        return QImage(48, 48, QImage.Format.Format_RGBA8888)

    def test_success_populates_row_and_clears_state(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m, _started = self._model(model_cls, p, monkeypatch)
        m._on_fetched(p, self._image(), 100, 80, 12.5, 1.0, True)  # noqa: SLF001
        _, row = m._row_index(p)  # noqa: SLF001
        assert row.fetched is True
        assert (row.width, row.height) == (100, 80)
        assert p not in m._in_flight  # noqa: SLF001
        assert p not in m._retry  # noqa: SLF001

    def test_transient_failure_requeues_without_caching(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m, started = self._model(model_cls, p, monkeypatch)
        m._on_fetched(p, self._image(), 0, 0, 0.0, 0.0, False)  # noqa: SLF001
        _, row = m._row_index(p)  # noqa: SLF001
        assert row.fetched is False           # not cached as a permanent blank
        assert m._retry[p] == 1               # noqa: SLF001
        assert p in m._in_flight              # re-queued  # noqa: SLF001
        assert len(started) == 1

    def test_failure_caps_then_falls_back_to_placeholder(self, list_mod, tmp_path, monkeypatch):
        from Imervue.gui.image_list_view import _MAX_THUMB_RETRIES
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m, _started = self._model(model_cls, p, monkeypatch)
        for _ in range(_MAX_THUMB_RETRIES):
            m._on_fetched(p, self._image(), 0, 0, 0.0, 0.0, False)  # noqa: SLF001
        assert m._row_index(p)[1].fetched is False  # noqa: SLF001
        # One failure past the cap caches the placeholder so it stops retrying.
        m._on_fetched(p, self._image(), 0, 0, 0.0, 0.0, False)  # noqa: SLF001
        _, row = m._row_index(p)  # noqa: SLF001
        assert row.fetched is True
        assert row.width is None and row.size_kb is None
        assert p not in m._retry  # noqa: SLF001

    def test_late_callback_for_removed_path_is_ignored(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m, _started = self._model(model_cls, p, monkeypatch)
        # A callback arriving after the folder changed must be a safe no-op.
        m._on_fetched(str(tmp_path / "gone.png"), self._image(),  # noqa: SLF001
                      1, 1, 1.0, 1.0, True)
        assert m._row_index(p)[1].fetched is False  # noqa: SLF001


def _run_list_thumb(path):
    from Imervue.gui.image_list_view import _ThumbWorker

    worker = _ThumbWorker(path)
    emitted: list = []
    worker.signals.done.connect(lambda *args: emitted.append(args))
    worker.run()   # the QRunnable body, inline
    return emitted


def test_list_thumb_missing_file_emits_failure_quietly(qapp, tmp_path, caplog):
    with caplog.at_level("DEBUG", logger="Imervue"):
        (args,) = _run_list_thumb(str(tmp_path / "gone.png"))
    assert args[-1] is False
    assert caplog.records == []


def test_list_thumb_bug_is_logged_and_still_emits(qapp, tmp_path, monkeypatch, caplog):
    from Imervue.gui import image_list_view

    path = tmp_path / "a.png"
    path.write_bytes(b"x")

    def broken(*_args, **_kwargs):
        raise RuntimeError("decoder bug")

    monkeypatch.setattr(image_list_view.Image, "open", broken)
    with caplog.at_level("DEBUG", logger="Imervue"):
        (args,) = _run_list_thumb(str(path))
    assert args[-1] is False
    (record,) = caplog.records
    assert record.exc_info[0] is RuntimeError


class TestRefetch:
    """A row whose file another program rewrote, removed or restored is read again."""

    @staticmethod
    def _fetched_model(model_cls, paths, monkeypatch):
        m = model_cls(paths)
        started: list = []
        monkeypatch.setattr(m._pool, "start", started.append)  # noqa: SLF001
        for p in paths:
            m._on_fetched(p, TestThumbFetchRetry._image(), 100, 80, 1.0, 1.0, True)  # noqa: SLF001
        return m, started

    def test_a_refetched_row_keeps_its_thumbnail_until_read_again(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        a, b = str(tmp_path / "a.png"), str(tmp_path / "b.png")
        m, started = self._fetched_model(model_cls, [a, b], monkeypatch)
        old_icon = m._row_index(b)[1].icon  # noqa: SLF001
        changed: list = []
        m.dataChanged.connect(lambda top, bottom, roles: changed.append((top.row(), bottom.row(), roles)))
        m.refetch({b})
        row = m._row_index(b)[1]  # noqa: SLF001
        assert row.fetched is False
        assert row.icon is old_icon
        assert changed == [(1, 1, [Qt.ItemDataRole.DecorationRole])]
        assert m._row_index(a)[1].fetched is True  # noqa: SLF001
        assert started == []          # nothing read until the row is painted
        m.data(m.index(1, m.COL_THUMB), Qt.ItemDataRole.DecorationRole)
        assert len(started) == 1

    def test_a_read_under_way_is_dropped_and_done_again(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m = model_cls([p])
        started: list = []
        monkeypatch.setattr(m._pool, "start", started.append)  # noqa: SLF001
        m.data(m.index(0, m.COL_THUMB), Qt.ItemDataRole.DecorationRole)
        assert len(started) == 1
        m.refetch([p])                # the file changed while it was being read
        m._on_fetched(p, TestThumbFetchRetry._image(), 100, 80, 1.0, 1.0, True)  # noqa: SLF001
        row = m._row_index(p)[1]  # noqa: SLF001
        assert row.fetched is False
        assert row.width is None      # the old read's result was not applied
        assert len(started) == 2
        m._on_fetched(p, TestThumbFetchRetry._image(), 120, 90, 1.0, 1.0, True)  # noqa: SLF001
        assert (row.fetched, row.width) == (True, 120)

    def test_refetch_resets_the_retry_budget(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m, _started = self._fetched_model(model_cls, [p], monkeypatch)
        m._retry[p] = 2  # noqa: SLF001
        m.refetch([p])
        assert p not in m._retry  # noqa: SLF001

    def test_paths_outside_the_list_are_ignored(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m, _started = self._fetched_model(model_cls, [p], monkeypatch)
        m.refetch([str(tmp_path / "elsewhere.png")])
        assert m._row_index(p)[1].fetched is True  # noqa: SLF001

    def test_a_new_folder_forgets_stale_reads(self, list_mod, tmp_path, monkeypatch):
        model_cls, _ = list_mod
        p = str(tmp_path / "a.png")
        m = model_cls([p])
        monkeypatch.setattr(m._pool, "start", lambda _worker: None)  # noqa: SLF001
        m.data(m.index(0, m.COL_THUMB), Qt.ItemDataRole.DecorationRole)
        m.refetch([p])
        m.set_paths([p])
        assert m._stale == set()  # noqa: SLF001


def test_an_external_save_shows_in_the_list(qapp, tmp_path, pump_until):
    from PIL import Image

    from Imervue.gui.image_list_view import ImageListView
    path = tmp_path / "a.png"
    Image.new("RGB", (40, 30), "red").save(path)
    view = ImageListView(main_window=None)
    try:
        model = view.model()
        view.set_paths([str(path)])
        index = model.index(0, model.COL_RES)
        model.data(model.index(0, model.COL_THUMB), Qt.ItemDataRole.DecorationRole)
        assert pump_until(lambda: model.data(index) == "40×30")
        Image.new("RGB", (64, 48), "blue").save(path)   # another program saves over it
        view.refetch({str(path)})
        model.data(model.index(0, model.COL_THUMB), Qt.ItemDataRole.DecorationRole)
        assert pump_until(lambda: model.data(index) == "64×48")
    finally:
        view.deleteLater()


def test_the_main_window_passes_changed_paths_to_the_list():
    from types import SimpleNamespace

    from Imervue.gui.main_window_browse import MainWindowBrowseMixin
    got: list = []
    window = SimpleNamespace(image_list_view=SimpleNamespace(refetch=got.append))
    MainWindowBrowseMixin.refetch_list_rows(window, {"a.png"})
    assert got == [{"a.png"}]



class _EditWindow:
    """Records what the list asks the main window to delete or undo."""

    def __init__(self):
        self.deleted: list = []
        self.undos = 0

    def delete_list_selection(self, paths):
        self.deleted.append(list(paths))

    def undo_from_list(self):
        self.undos += 1


def _press(view, key, modifiers=Qt.KeyboardModifier.NoModifier):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers)
    event.ignore()   # a new event starts accepted: make the handler say so itself
    view.keyPressEvent(event)
    return event


def _list_with(qapp, tmp_path, names, window):
    from PySide6.QtCore import QItemSelectionModel

    from Imervue.gui.image_list_view import ImageListView
    view = ImageListView(main_window=window)
    view.set_paths([str(tmp_path / name) for name in names])
    return view, QItemSelectionModel


def test_delete_in_the_list_deletes_the_selected_rows(qapp, tmp_path):
    """Delete did nothing in the List view: only the wall and Deep Zoom listened for it."""
    window = _EditWindow()
    view, selection = _list_with(qapp, tmp_path, ["a.png", "b.png", "c.png"], window)
    try:
        model = view.model()
        flags = selection.SelectionFlag.Select | selection.SelectionFlag.Rows
        view.selectionModel().select(model.index(0, 0), flags)
        view.selectionModel().select(model.index(1, 0), flags)
        event = _press(view, Qt.Key.Key_Delete)
    finally:
        view.deleteLater()
    assert window.deleted == [[str(tmp_path / "a.png"), str(tmp_path / "b.png")]]
    assert event.isAccepted()


def test_delete_moves_the_cursor_to_the_row_that_takes_their_place(qapp, tmp_path):
    names = ["a.png", "b.png", "c.png"]
    view, selection = _list_with(qapp, tmp_path, names, None)

    class _Window(_EditWindow):
        def delete_list_selection(self, paths):
            super().delete_list_selection(paths)
            view.set_paths([str(tmp_path / n) for n in names if str(tmp_path / n) not in paths])

    view._main_window = _Window()  # noqa: SLF001
    try:
        view.selectRow(1)
        _press(view, Qt.Key.Key_Delete)
        assert view.selected_paths() == [str(tmp_path / "c.png")]
    finally:
        view.deleteLater()


def test_ctrl_z_in_the_list_undoes(qapp, tmp_path):
    window = _EditWindow()
    view, _selection = _list_with(qapp, tmp_path, ["a.png"], window)
    try:
        event = _press(view, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    finally:
        view.deleteLater()
    assert window.undos == 1
    assert event.isAccepted()


def test_delete_with_nothing_selected_does_nothing(qapp, tmp_path):
    window = _EditWindow()
    view, _selection = _list_with(qapp, tmp_path, ["a.png"], window)
    try:
        view.clearSelection()
        _press(view, Qt.Key.Key_Delete)
    finally:
        view.deleteLater()
    assert window.deleted == []


def test_a_rebound_delete_key_is_followed(qapp, tmp_path, monkeypatch):
    from Imervue.gui.shortcut_settings_dialog import shortcut_manager
    window = _EditWindow()
    monkeypatch.setattr(shortcut_manager, "get_action",
                        lambda key, _mods: "delete" if key == Qt.Key.Key_X else None)
    view, _selection = _list_with(qapp, tmp_path, ["a.png"], window)
    try:
        view.selectRow(0)
        _press(view, Qt.Key.Key_Delete)
        assert window.deleted == []
        _press(view, Qt.Key.Key_X)
    finally:
        view.deleteLater()
    assert window.deleted == [[str(tmp_path / "a.png")]]


def test_a_list_without_a_main_window_ignores_delete(qapp, tmp_path):
    view, _selection = _list_with(qapp, tmp_path, ["a.png"], None)
    try:
        view.selectRow(0)
        _press(view, Qt.Key.Key_Delete)   # must not raise
    finally:
        view.deleteLater()


def test_the_main_window_deletes_the_list_rows_like_the_wall(monkeypatch):
    from types import SimpleNamespace

    from Imervue.gpu_image_view.actions import delete
    from Imervue.gui.main_window_browse import MainWindowBrowseMixin
    seen, refreshed = [], []
    monkeypatch.setattr(delete, "delete_selected_tiles",
                        lambda viewer: seen.append(set(viewer.selected_tiles)))
    viewer = SimpleNamespace(selected_tiles={"stale.png"})
    window = SimpleNamespace(viewer=viewer, refresh_list_view=lambda: refreshed.append(True))
    MainWindowBrowseMixin.delete_list_selection(window, ["a.png", "b.png"])
    assert seen == [{"a.png", "b.png"}]
    assert refreshed == [True]


def test_undo_from_the_list_runs_the_viewers_undo_and_shows_the_rows(monkeypatch):
    from types import SimpleNamespace

    from Imervue.gui.main_window_browse import MainWindowBrowseMixin
    actions, refreshed = [], []
    viewer = SimpleNamespace(run_shortcut_action=actions.append)
    window = SimpleNamespace(viewer=viewer, refresh_list_view=lambda: refreshed.append(True))
    MainWindowBrowseMixin.undo_from_list(window)
    assert actions == ["undo"]
    assert refreshed == [True]
