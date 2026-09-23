"""Tests for restoring the main window's saved geometry and state."""
from __future__ import annotations

import base64

import pytest
from PySide6.QtWidgets import QMainWindow

from Imervue.gui.main_window_screens import MainWindowScreensMixin
from Imervue.user_settings.user_setting_dict import user_setting_dict


class _Window(MainWindowScreensMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    def showMaximized(self):  # noqa: N802 - Qt naming
        self.calls.append("maximized")

    def showNormal(self):  # noqa: N802 - Qt naming
        self.calls.append("normal")


@pytest.fixture
def window(qapp, monkeypatch):
    for key in ("window_geometry", "window_state", "window_maximized"):
        monkeypatch.delitem(user_setting_dict, key, raising=False)
    win = _Window()
    yield win
    win.deleteLater()


def test_no_saved_geometry_maximizes(window):
    window._restore_window_geometry()  # noqa: SLF001
    assert window.calls == ["maximized"]


@pytest.mark.parametrize("saved", ["%%% not base64 %%%", 12345, ["list"]])
def test_undecodable_geometry_maximizes(window, saved):
    user_setting_dict["window_geometry"] = saved
    window._restore_window_geometry()  # noqa: SLF001
    assert window.calls == ["maximized"]


@pytest.mark.parametrize("state", ["%%% not base64 %%%", 12345])
def test_undecodable_state_is_ignored(window, monkeypatch, state):
    user_setting_dict["window_geometry"] = base64.b64encode(window.saveGeometry().data()).decode()
    user_setting_dict["window_state"] = state
    user_setting_dict["window_maximized"] = False
    monkeypatch.setattr(_Window, "_geometry_on_visible_screen", lambda self: True)
    window._restore_window_geometry()  # noqa: SLF001
    assert window.calls == ["normal"]


def test_unexpected_decode_error_propagates(window, monkeypatch):
    def boom(_data):
        raise RuntimeError("bug")

    monkeypatch.setattr(base64, "b64decode", boom)
    user_setting_dict["window_geometry"] = "AAAA"
    with pytest.raises(RuntimeError):
        window._restore_window_geometry()  # noqa: SLF001
