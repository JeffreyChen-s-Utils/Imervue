"""Tests for the image-tab strip's right-click context menu and the
file-tree rename / duplicate helpers — phase 34a UX wiring.

The tab-strip wiring is exercised via the ``_close_tabs_*`` helpers
directly (the QMenu.exec call is hard to drive headlessly, but the
helpers are the actual surface that needs to be correct). The
file-tree helpers are exercised via the module-level
``_next_duplicate_name`` and via stub ``_FileTreeView`` instances
that drive ``_rename_path`` / ``_duplicate_file`` against a
``tmp_path`` sandbox.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Imervue.Imervue_main_window import _FileTreeView, _next_duplicate_name


# ---------------------------------------------------------------------------
# _next_duplicate_name — pure helper
# ---------------------------------------------------------------------------


def test_next_duplicate_name_picks_copy_suffix(tmp_path: Path):
    src = tmp_path / "photo.png"
    src.write_bytes(b"x")
    assert _next_duplicate_name(src) == tmp_path / "photo (copy).png"


def test_next_duplicate_name_avoids_existing_copy(tmp_path: Path):
    src = tmp_path / "note.txt"
    src.write_text("a")
    (tmp_path / "note (copy).txt").write_text("a")
    assert _next_duplicate_name(src) == tmp_path / "note (copy 2).txt"


def test_next_duplicate_name_walks_until_free(tmp_path: Path):
    src = tmp_path / "x.dat"
    src.write_bytes(b"")
    (tmp_path / "x (copy).dat").write_bytes(b"")
    (tmp_path / "x (copy 2).dat").write_bytes(b"")
    assert _next_duplicate_name(src) == tmp_path / "x (copy 3).dat"


def test_next_duplicate_name_handles_no_extension(tmp_path: Path):
    src = tmp_path / "README"
    src.write_text("hi")
    assert _next_duplicate_name(src) == tmp_path / "README (copy)"


# ---------------------------------------------------------------------------
# _FileTreeView rename / duplicate happy paths
# ---------------------------------------------------------------------------


class _StubToast:
    """Minimal toast stand-in that records every notification."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def info(self, text, duration_ms=2500):
        self.calls.append(("info", text))

    def success(self, text, duration_ms=2500):
        self.calls.append(("success", text))

    def warning(self, text, duration_ms=4000):
        self.calls.append(("warning", text))

    def error(self, text, duration_ms=4000):
        self.calls.append(("error", text))


class _StubMainWindow:
    """Just carries a ``.toast`` so the tree-view methods can ping it."""

    def __init__(self):
        self.toast = _StubToast()


@pytest.fixture
def tree_view(qapp, monkeypatch):
    main = _StubMainWindow()
    view = _FileTreeView(main)
    # Bypass the actual QFileSystemModel — _refresh_tree assumes one.
    monkeypatch.setattr(view, "_refresh_tree", lambda: None)
    yield view
    view.deleteLater()


def test_duplicate_file_creates_copy(qapp, tmp_path, tree_view, monkeypatch):
    src = tmp_path / "img.png"
    src.write_bytes(b"hello")
    tree_view._duplicate_file(str(src))   # noqa: SLF001
    expected = tmp_path / "img (copy).png"
    assert expected.exists()
    assert expected.read_bytes() == b"hello"
    # Toast confirmation lands on the stub main window.
    msgs = tree_view._main_window.toast.calls   # noqa: SLF001
    assert msgs and msgs[0][0] == "success"
    assert "img (copy).png" in msgs[0][1]


def test_duplicate_file_silent_for_directory(qapp, tmp_path, tree_view):
    folder = tmp_path / "subdir"
    folder.mkdir()
    tree_view._duplicate_file(str(folder))   # noqa: SLF001
    # No copy, no toast — duplicate is a file-only verb.
    assert not (tmp_path / "subdir (copy)").exists()
    assert tree_view._main_window.toast.calls == []   # noqa: SLF001


def test_rename_path_renames_file(qapp, tmp_path, tree_view, monkeypatch):
    src = tmp_path / "old.png"
    src.write_bytes(b"")
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *a, **k: ("new.png", True),
    )
    tree_view._rename_path(str(src))   # noqa: SLF001
    assert not src.exists()
    assert (tmp_path / "new.png").exists()
    msgs = tree_view._main_window.toast.calls   # noqa: SLF001
    assert msgs and msgs[0][0] == "success"


def test_rename_path_cancelled(qapp, tmp_path, tree_view, monkeypatch):
    src = tmp_path / "keep.png"
    src.write_bytes(b"")
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *a, **k: ("ignored.png", False),
    )
    tree_view._rename_path(str(src))   # noqa: SLF001
    assert src.exists()
    assert tree_view._main_window.toast.calls == []   # noqa: SLF001


def test_rename_path_blank_name_is_noop(qapp, tmp_path, tree_view, monkeypatch):
    src = tmp_path / "x.txt"
    src.write_text("hi")
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *a, **k: ("   ", True),
    )
    tree_view._rename_path(str(src))   # noqa: SLF001
    assert src.exists()
    assert tree_view._main_window.toast.calls == []   # noqa: SLF001


def test_rename_path_collides_with_existing(qapp, tmp_path, tree_view, monkeypatch):
    src = tmp_path / "a.txt"
    src.write_text("a")
    (tmp_path / "b.txt").write_text("b")
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *a, **k: ("b.txt", True),
    )
    tree_view._rename_path(str(src))   # noqa: SLF001
    # Original survives, conflicting file untouched.
    assert src.exists()
    assert (tmp_path / "b.txt").read_text() == "b"
    msgs = tree_view._main_window.toast.calls   # noqa: SLF001
    assert msgs and msgs[0][0] == "warning"


def test_rename_path_missing_source_silent(qapp, tmp_path, tree_view, monkeypatch):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *a, **k: ("any.txt", True),
    )
    tree_view._rename_path(str(tmp_path / "ghost.txt"))   # noqa: SLF001
    assert tree_view._main_window.toast.calls == []   # noqa: SLF001


# ---------------------------------------------------------------------------
# Tab-strip close helpers — exercised on a stub-bound main window
# ---------------------------------------------------------------------------


class _FakeTabBar:
    """Minimal ``QTabBar`` stand-in. The close helpers call ``removeTab``
    and ``currentIndex`` only, which we mirror with a simple list."""

    def __init__(self):
        self.tabs: list[str] = []

    def addTab(self, label: str) -> int:
        self.tabs.append(label)
        return len(self.tabs) - 1

    def removeTab(self, idx: int) -> None:
        if 0 <= idx < len(self.tabs):
            self.tabs.pop(idx)

    def currentIndex(self) -> int:
        return -1 if not self.tabs else 0

    def count(self) -> int:
        return len(self.tabs)


class _CloseHelperHost:
    """Mounts the ``_close_tabs_*`` methods onto a tiny stand-in so we
    can drive them in isolation. The real owner is ImervueMainWindow,
    which costs >1s to construct under the qapp fixture."""

    def __init__(self, n: int):
        self._image_tabs = [{"path": f"/p/{i}.png", "title": f"t{i}"} for i in range(n)]
        self._tab_bar = _FakeTabBar()
        for entry in self._image_tabs:
            self._tab_bar.addTab(entry["title"])
        self._tab_switching = False

    def _on_tab_close(self, idx: int) -> None:
        if 0 <= idx < len(self._image_tabs):
            self._image_tabs.pop(idx)
            self._tab_bar.removeTab(idx)

    # Bind the production helpers under test.
    from Imervue.Imervue_main_window import ImervueMainWindow as _RealMW
    _close_tabs_except = _RealMW._close_tabs_except
    _close_tabs_after = _RealMW._close_tabs_after
    _close_all_tabs = _RealMW._close_all_tabs


def test_close_tabs_except_keeps_only_selected(qapp):
    host = _CloseHelperHost(4)
    host._close_tabs_except(2)   # noqa: SLF001
    assert len(host._image_tabs) == 1   # noqa: SLF001
    assert host._image_tabs[0]["title"] == "t2"   # noqa: SLF001


def test_close_tabs_except_out_of_range_is_noop(qapp):
    host = _CloseHelperHost(3)
    host._close_tabs_except(99)   # noqa: SLF001
    assert len(host._image_tabs) == 3   # noqa: SLF001


def test_close_tabs_after_drops_right_only(qapp):
    host = _CloseHelperHost(5)
    host._close_tabs_after(1)   # noqa: SLF001
    assert [e["title"] for e in host._image_tabs] == ["t0", "t1"]   # noqa: SLF001


def test_close_tabs_after_last_index_is_noop(qapp):
    host = _CloseHelperHost(3)
    host._close_tabs_after(2)   # noqa: SLF001
    assert len(host._image_tabs) == 3   # noqa: SLF001


def test_close_all_tabs_empties_the_strip(qapp):
    host = _CloseHelperHost(4)
    host._close_all_tabs()   # noqa: SLF001
    assert host._image_tabs == []   # noqa: SLF001


# ---------------------------------------------------------------------------
# New-folder success toast — phase 34f
# ---------------------------------------------------------------------------


def test_create_new_folder_emits_success_toast(qapp, tmp_path, tree_view, monkeypatch):
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *a, **k: ("snaps", True),
    )
    tree_view._create_new_folder(str(tmp_path))   # noqa: SLF001
    assert (tmp_path / "snaps").is_dir()
    msgs = tree_view._main_window.toast.calls   # noqa: SLF001
    assert msgs and msgs[0][0] == "success"
    assert "snaps" in msgs[0][1]


def test_create_new_folder_existing_emits_warning(qapp, tmp_path, tree_view, monkeypatch):
    (tmp_path / "exists").mkdir()
    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getText",
        lambda *a, **k: ("exists", True),
    )
    tree_view._create_new_folder(str(tmp_path))   # noqa: SLF001
    msgs = tree_view._main_window.toast.calls   # noqa: SLF001
    assert msgs and msgs[0][0] == "warning"


# ---------------------------------------------------------------------------
# Open with default app — phase 34h
# ---------------------------------------------------------------------------


def test_open_with_default_app_calls_qdesktopservices(qapp, tmp_path, tree_view, monkeypatch):
    src = tmp_path / "doc.png"
    src.write_bytes(b"")
    captured = {}

    def fake_open_url(url):
        captured["url"] = url
        return True   # success — toast suppressed

    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", fake_open_url)
    tree_view._open_with_default_app(str(src))   # noqa: SLF001
    assert "url" in captured
    # Qt normalises the URL's local-file path to forward slashes; both
    # representations point at the same file.
    assert Path(captured["url"].toLocalFile()) == src
    assert tree_view._main_window.toast.calls == []   # noqa: SLF001


def test_open_with_default_app_failure_emits_error_toast(
    qapp, tmp_path, tree_view, monkeypatch,
):
    src = tmp_path / "broken.png"
    src.write_bytes(b"")
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    tree_view._open_with_default_app(str(src))   # noqa: SLF001
    msgs = tree_view._main_window.toast.calls   # noqa: SLF001
    assert msgs and msgs[0][0] == "error"
    assert "broken.png" in msgs[0][1]


# ---------------------------------------------------------------------------
# Tab "Reveal in File Tree" — phase 35d
# ---------------------------------------------------------------------------


class _RevealHost:
    """Mounts ``_reveal_path_in_tree`` onto a tiny stand-in so we can
    drive it without booting the full ImervueMainWindow."""

    def __init__(self, qapp):
        self.toast = _StubToast()
        self.tree = self._FakeTree()
        self.model = self._FakeModel()

    class _FakeTree:
        def __init__(self):
            self.scroll_to_calls = []
            self.current_set = None
            self.focused = False

        def scrollTo(self, index):
            self.scroll_to_calls.append(index)

        def setCurrentIndex(self, index):
            self.current_set = index

        def setFocus(self):
            self.focused = True

    class _FakeModel:
        def index(self, path):
            self.last_path = path
            # The helper checks ``.isValid()`` on the returned index;
            # we hand back a dummy that reports True so the call
            # progresses to scrollTo / setCurrentIndex.
            return _ValidIndex()

    from Imervue.Imervue_main_window import ImervueMainWindow as _RealMW
    _reveal_path_in_tree = _RealMW._reveal_path_in_tree


class _ValidIndex:
    def isValid(self):
        return True


def test_reveal_path_in_tree_selects_row(qapp, tmp_path):
    src = tmp_path / "shot.png"
    src.write_bytes(b"")
    host = _RevealHost(qapp)
    host._reveal_path_in_tree(str(src))   # noqa: SLF001
    assert host.tree.scroll_to_calls
    assert host.tree.current_set is not None
    assert host.tree.focused
    assert host.toast.calls == []


def test_reveal_path_in_tree_missing_file_emits_warning(qapp, tmp_path):
    host = _RevealHost(qapp)
    host._reveal_path_in_tree(str(tmp_path / "ghost.png"))   # noqa: SLF001
    assert host.toast.calls and host.toast.calls[0][0] == "warning"
    # The warning includes the basename so the user knows which tab.
    assert "ghost.png" in host.toast.calls[0][1]


def test_reveal_path_in_tree_empty_path_is_noop(qapp):
    host = _RevealHost(qapp)
    host._reveal_path_in_tree("")   # noqa: SLF001
    assert host.tree.scroll_to_calls == []
    assert host.toast.calls == []


# ---------------------------------------------------------------------------
# F2 rename keypress on the tree view
# ---------------------------------------------------------------------------


def test_f2_keypress_invokes_rename(qapp, tmp_path, tree_view, monkeypatch):
    """Pressing F2 with a selection should call _rename_path so users
    don't have to right-click to rename. The tree view's keyPressEvent
    routes F2 through a dedicated helper."""
    src = tmp_path / "before.txt"
    src.write_text("x")

    captured = {}

    def fake_rename(path):
        captured["path"] = path

    monkeypatch.setattr(tree_view, "_rename_path", fake_rename)

    # _rename_selected reads selectedIndexes from the model — stub it.
    class _Idx:
        pass

    class _SelectionModel:
        def selectedIndexes(self):
            return [_Idx()]

    monkeypatch.setattr(tree_view, "selectionModel", lambda: _SelectionModel())

    class _Model:
        def filePath(self, _idx):
            return str(src)

    monkeypatch.setattr(tree_view, "model", lambda: _Model())

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    evt = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
    tree_view.keyPressEvent(evt)
    assert captured.get("path") == str(src)
