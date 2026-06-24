"""Tests for the recent-files menu UX hardening — phase 35c.

Coverage:

* ``_drop_missing_recent`` removes a path from both folder + image lists.
* ``open_recent`` against a missing path emits a warning toast and
  drops the stale entry rather than failing silently.
* Menu items show the basename for scannability and the full path in
  the tooltip / status tip.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMenu

from tests._toast_spy import ToastSpy as _ToastSpy
from Imervue.menu.recent_menu import (
    _drop_missing_recent,
    build_recent_menu,
    open_recent,
    rebuild_recent_menu,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _reset_recent_settings():
    keys = ("user_recent_folders", "user_recent_images", "user_last_folder")
    for k in keys:
        user_setting_dict.pop(k, None)
    yield
    for k in keys:
        user_setting_dict.pop(k, None)


# ---------------------------------------------------------------------------
# _drop_missing_recent — pure helper
# ---------------------------------------------------------------------------


def test_drop_missing_removes_from_folders():
    user_setting_dict["user_recent_folders"] = ["/a", "/b", "/c"]
    _drop_missing_recent("/b")
    assert user_setting_dict["user_recent_folders"] == ["/a", "/c"]


def test_drop_missing_removes_from_images():
    user_setting_dict["user_recent_images"] = ["/x.png", "/y.jpg"]
    _drop_missing_recent("/y.jpg")
    assert user_setting_dict["user_recent_images"] == ["/x.png"]


def test_drop_missing_silent_when_path_absent():
    user_setting_dict["user_recent_folders"] = ["/keep"]
    _drop_missing_recent("/never_existed")
    assert user_setting_dict["user_recent_folders"] == ["/keep"]


# ---------------------------------------------------------------------------
# open_recent against a missing path — toast + self-heal
# ---------------------------------------------------------------------------


class _StubViewer:
    def clear_tile_grid(self):
        """No-op — the rebuild path doesn't actually paint."""


class _StubModel:
    """Stand-in for ``QFileSystemModel`` — names mirror Qt's API on
    purpose so the production code can call them as if they were real."""

    def fileIcon(self, _index):   # noqa: N802  # NOSONAR — mirrors QFileSystemModel.fileIcon
        """Return a blank icon — tests don't compare icon pixels."""
        from PySide6.QtGui import QIcon
        return QIcon()

    def index(self, _path):
        """Return a default QModelIndex — invalid is fine for the
        rebuild path which only needs ``valid()``-style fallthrough."""
        from PySide6.QtCore import QModelIndex
        return QModelIndex()

    def setRootPath(self, _path):   # noqa: N802  # NOSONAR — mirrors QFileSystemModel.setRootPath
        """No-op — open_recent calls this on real models to switch
        the tree root, but the test stub only records side effects
        elsewhere."""


class _StubMainWindow:
    """Bare attributes ``open_recent`` and ``rebuild_recent_menu`` need."""

    def __init__(self, qapp):
        self.toast = _ToastSpy()
        self.viewer = _StubViewer()
        self.model = _StubModel()
        self.tree = _StubTree()
        self._recent_folder_menu = QMenu()
        self._recent_image_menu = QMenu()
        self._recent_menu = QMenu()


class _StubTree:
    def setRootIndex(self, _index):   # noqa: N802  # NOSONAR — mirrors QTreeView.setRootIndex
        """No-op — the test asserts on settings + toast, not on
        the tree's selection state."""


def test_open_recent_missing_path_emits_warning_toast(qapp, tmp_path):
    main = _StubMainWindow(qapp)
    user_setting_dict["user_recent_images"] = [str(tmp_path / "ghost.png")]
    open_recent(main, str(tmp_path / "ghost.png"))
    assert main.toast.calls and main.toast.calls[0][0] == "warning"
    # Self-heal: stale path is dropped from the recents.
    assert user_setting_dict["user_recent_images"] == []


def test_open_recent_missing_path_no_toast_attr_does_not_crash(qapp, tmp_path):
    """Older embedders may not yet have a ``.toast`` attribute — the
    self-heal must still run without raising."""
    user_setting_dict["user_recent_folders"] = [str(tmp_path / "ghost-dir")]
    main = _StubMainWindow(qapp)
    del main.toast
    open_recent(main, str(tmp_path / "ghost-dir"))
    assert user_setting_dict["user_recent_folders"] == []


# ---------------------------------------------------------------------------
# Menu rebuild surfaces basenames + tooltips
# ---------------------------------------------------------------------------


def test_rebuild_uses_basename_label_and_full_path_tooltip(qapp, tmp_path):
    """A long path should render as just its basename so the menu stays
    scannable; the full path lands in the tooltip / status tip."""
    folder = tmp_path / "deeply" / "nested" / "albums"
    folder.mkdir(parents=True)
    user_setting_dict["user_recent_folders"] = [str(folder)]

    main = _StubMainWindow(qapp)
    rebuild_recent_menu(main)
    actions = main._recent_folder_menu.actions()
    assert actions
    assert actions[0].text() == "albums"
    assert actions[0].toolTip() == str(folder)


def test_rebuild_marks_empty_when_no_recents(qapp):
    main = _StubMainWindow(qapp)
    rebuild_recent_menu(main)
    folder_actions = main._recent_folder_menu.actions()
    assert folder_actions
    # The single placeholder action is disabled so users can't click it.
    assert not folder_actions[0].isEnabled()


def test_build_recent_menu_includes_clear_action(qapp):
    """The full builder mounts a top-level ``Clear Recent`` action so the
    user can wipe the lists without editing settings by hand."""
    main = _StubMainWindow(qapp)
    parent = QMenu()
    build_recent_menu(main, parent)
    titles = [a.text() for a in main._recent_menu.actions() if a.text()]
    assert any("Clear" in t for t in titles)


# ---------------------------------------------------------------------------
# Teardown safety — the C++ side of the submenus may be deleted before
# the next ``rebuild_recent_menu`` call lands.
# ---------------------------------------------------------------------------


class _DeletedMenuStub:
    """Stands in for a QMenu whose underlying C++ object has been
    freed. Every method that touches Qt raises ``RuntimeError`` the
    same way shiboken does."""

    def clear(self):
        raise RuntimeError(
            "libshiboken: Internal C++ object (PySide6.QtWidgets.QMenu) "
            "already deleted.",
        )

    def addAction(self, *_args, **_kwargs):  # NOSONAR
        raise RuntimeError("already deleted")

    def setToolTipsVisible(self, *_args, **_kwargs):  # NOSONAR
        raise RuntimeError("already deleted")


class _ShutdownMainWindow:
    """Stub main window whose recent submenus are dead wrappers."""

    def __init__(self):
        self._recent_folder_menu = _DeletedMenuStub()
        self._recent_image_menu = _DeletedMenuStub()
        self.model = _StubModel()


def test_rebuild_silent_when_menus_already_deleted():
    """During GUI close, ``on_file_clicked`` can fire after Qt has
    freed the recent-submenu C++ objects. Without this guard,
    ``folder_menu.clear()`` raised the libshiboken error all the
    way through the close handler and dumped a traceback the user
    saw in the terminal. The guard swallows that specific case
    silently — there's no menu left to refresh."""
    main = _ShutdownMainWindow()
    user_setting_dict["user_recent_folders"] = ["/some/path"]
    user_setting_dict["user_recent_images"] = ["/some/image.jpg"]
    rebuild_recent_menu(main)   # must not raise


def test_rebuild_silent_when_menu_attrs_missing():
    """A partially-constructed window (e.g. an exception in the
    File-menu build path) leaves the recent submenu attrs unset.
    Any subsequent ``rebuild_recent_menu`` call must short-circuit
    rather than ``AttributeError`` out."""
    class _BareMainWindow:
        pass
    rebuild_recent_menu(_BareMainWindow())   # must not raise
