"""Contract tests for the desktop-pet workspace tab's handlers and wiring.

Pins what the Desktop Pet tab's slots do — which pet setter each toggle drives,
the failure messages and quiet un-ticking for the optional-dependency drivers,
rig / script loading feedback, the hotkey edit paths, the lazy overlay creation
and the session restore — on a light host object that borrows the real methods,
so no :class:`PetWindow` (a ``QOpenGLWidget``) is ever built. Also pins the
public names the module exposes and the class layout ahead of ``QWidget``.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QCheckBox, QComboBox, QKeySequenceEdit, QLabel, QTabWidget, QWidget

from Imervue.desktop_pet import pet_workspace as mod
from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.hotkey_manager import (
    ACTION_SPEAK_NOW,
    ACTION_TOGGLE_VISIBLE,
    DEFAULT_HOTKEY_BINDINGS,
)
from Imervue.desktop_pet.pet_workspace import PetWorkspace

_STALE = "stale"

# Instance methods the host borrows from PetWorkspace.
_BORROWED = (
    "_restore_persisted_session", "_reapply_persisted_toggles", "_format_script_label",
    "load_puppet", "_on_open_example", "load_script", "_on_reset_script",
    "_on_show_toggled", "_on_pet_visibility_changed", "_on_click_through_toggled",
    "_on_anchor_toggled", "_on_always_on_bottom_toggled", "_on_fullscreen_toggled",
    "_on_speech_toggled", "_on_opacity_changed", "_on_snap_changed", "_on_size_changed",
    "_on_idle_toggled", "_on_idle_motion_toggled", "_on_blink_toggled", "_on_drag_toggled",
    "_on_gaze_toggled", "_on_hotkeys_toggled", "_on_hotkey_edited", "_on_mic_toggled",
    "_on_webcam_toggled", "pet_window", "attach_tray",
)

_DRIVER_BOXES = ("_idle_check", "_idle_motion_check", "_blink_check", "_drag_check",
                 "_gaze_check", "_mic_check", "_webcam_check")


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


class _FakePet:
    """Records every setter call; ``ok`` is what the setters and loaders return."""

    def __init__(self, *, ok: bool = True) -> None:
        self.calls: list[tuple] = []
        self.ok = ok
        self.hotkeys_on = False

    def __getattr__(self, name: str):
        if not name.startswith("set_"):
            raise AttributeError(name)

        def record(*args):
            self.calls.append((name, *args))
            return self.ok
        return record

    def load_puppet_file(self, path):
        self.calls.append(("load_puppet_file", path))
        return self.ok

    def load_script_file(self, path):
        self.calls.append(("load_script_file", path))
        return self.ok

    def reset_script_to_default(self):
        self.calls.append(("reset_script_to_default",))

    def show(self):
        self.calls.append(("show",))

    def hide(self):
        self.calls.append(("hide",))

    def hotkeys_enabled(self):
        return self.hotkeys_on


class _Host:
    """Just the widgets the borrowed methods touch; never builds a PetWindow."""

    def __init__(self, pet=None, *, tray=None) -> None:
        self._pet_window = pet
        self._tray = tray
        self.ensured = 0
        self.toggled: list[tuple[str, bool]] = []
        self._status = QLabel(_STALE)
        self._current_rig_label = QLabel()
        self._current_script_label = QLabel()
        self._opacity_label = QLabel()
        for attr in ("_show_check", "_hotkey_check", *_DRIVER_BOXES):
            box = QCheckBox()
            box.toggled.connect(lambda checked, name=attr: self.toggled.append((name, checked)))
            setattr(self, attr, box)

    def _ensure_pet_window(self):
        self.ensured += 1
        return self._pet_window


for _name in _BORROWED:
    setattr(_Host, _name, getattr(PetWorkspace, _name))


@pytest.fixture
def pet():
    return _FakePet()


@pytest.fixture
def host(qapp, pet):
    return _Host(pet)


# ---- public surface and class layout ---------------------------------


@pytest.mark.parametrize("name", [
    "PetWorkspace", "PetWindow", "saved_hotkeys", "hotkey_conflict_notice",
    "DEFAULT_EXAMPLE_PUPPET", "_resolve_bundled_example", "_WINDOW_CHECKS",
    "_DRIVER_CHECKS", "pet_settings", "language_wrapper",
])
def test_the_module_keeps_its_public_names(name):
    assert hasattr(mod, name)


def test_every_handler_resolves_ahead_of_qwidget():
    mro = PetWorkspace.__mro__
    qwidget = mro.index(QWidget)
    for name in (*_BORROWED, "_ensure_pet_window", "_on_pet_setting_changed", "_build_ui",
                 "_window_check", "_on_show_on_launch_toggled", "_build_hotkey_group"):
        owner = next(cls for cls in mro if name in cls.__dict__)
        assert mro.index(owner) < qwidget, name


def test_only_the_tab_itself_defines_init_and_the_signal():
    mro = PetWorkspace.__mro__
    for cls in mro[1:mro.index(QWidget)]:
        assert "__init__" not in cls.__dict__, cls
    assert "pet_created" in PetWorkspace.__dict__
    for name in ("_window_check", "_on_show_on_launch_toggled"):
        owner = next(cls for cls in mro if name in cls.__dict__)
        assert isinstance(owner.__dict__[name], staticmethod), name


# ---- window toggles ----------------------------------------------------


def test_show_toggle_shows_then_hides(host, pet):
    host._on_show_toggled(True)
    host._on_show_toggled(False)
    assert pet.calls == [("show",), ("hide",)]


def test_visibility_change_ticks_show_quietly(host):
    host._on_pet_visibility_changed(True)
    assert host._show_check.isChecked()
    assert host.toggled == []


def test_show_on_launch_is_persisted():
    PetWorkspace._on_show_on_launch_toggled(1)
    assert pet_settings.load()["show_on_launch"] is True
    PetWorkspace._on_show_on_launch_toggled(0)
    assert pet_settings.load()["show_on_launch"] is False


@pytest.mark.parametrize(("handler", "setter"), [
    ("_on_anchor_toggled", "set_anchor_locked"),
    ("_on_always_on_bottom_toggled", "set_always_on_bottom"),
    ("_on_fullscreen_toggled", "set_hide_on_fullscreen"),
    ("_on_speech_toggled", "set_speech_enabled"),
    ("_on_click_through_toggled", "set_click_through"),
    ("_on_idle_toggled", "set_auto_idle_enabled"),
    ("_on_idle_motion_toggled", "set_idle_motion_enabled"),
    ("_on_blink_toggled", "set_auto_blink_enabled"),
    ("_on_drag_toggled", "set_drag_track_enabled"),
    ("_on_gaze_toggled", "set_mouse_gaze_enabled"),
])
def test_each_toggle_drives_its_pet_setter_with_a_bool(host, pet, handler, setter):
    getattr(host, handler)(1)
    getattr(host, handler)(0)
    assert pet.calls == [(setter, True), (setter, False)]


@pytest.mark.parametrize(("percent", "label", "value"), [
    (5, "10%", 0.1), (55, "55%", 0.55), (100, "100%", 1.0), (150, "100%", 1.0),
])
def test_opacity_is_clamped_and_shown(host, pet, percent, label, value):
    host._on_opacity_changed(percent)
    assert host._opacity_label.text() == label
    assert pet.calls == [("set_pet_opacity", pytest.approx(value))]


def test_snap_threshold_is_passed_as_int(host, pet):
    host._on_snap_changed(7.0)
    assert pet.calls == [("set_snap_threshold", 7)]
    assert isinstance(pet.calls[0][1], int)


def test_size_change_needs_an_existing_pet(qapp, pet):
    without = _Host(None)
    without._on_size_changed("large")
    assert without.ensured == 0
    with_pet = _Host(pet)
    with_pet._on_size_changed("large")
    assert with_pet.ensured == 0
    assert pet.calls == [("set_size_preset", "large")]


# ---- optional-dependency drivers -------------------------------------


@pytest.mark.parametrize(("handler", "box", "setter", "message"), [
    ("_on_mic_toggled", "_mic_check", "set_mic_lipsync_enabled",
     "Mic lip-sync needs sounddevice — pip install sounddevice"),
    ("_on_webcam_toggled", "_webcam_check", "set_webcam_tracking_enabled",
     "Webcam tracking needs opencv-python + mediapipe"),
    ("_on_hotkeys_toggled", "_hotkey_check", "set_hotkeys_enabled",
     "Global hotkeys need pynput — pip install pynput"),
])
def test_a_missing_dependency_unticks_quietly_and_says_why(qapp, handler, box, setter, message):
    pet = _FakePet(ok=False)
    host = _Host(pet)
    getattr(host, box).blockSignals(True)
    getattr(host, box).setChecked(True)
    getattr(host, box).blockSignals(False)
    getattr(host, handler)(True)
    assert pet.calls == [(setter, True)]
    assert host._status.text() == message
    assert not getattr(host, box).isChecked()
    assert host.toggled == []


@pytest.mark.parametrize("handler", ["_on_mic_toggled", "_on_webcam_toggled",
                                     "_on_hotkeys_toggled"])
def test_a_driver_that_starts_or_is_turned_off_leaves_the_status(qapp, handler):
    getattr(_Host(_FakePet(ok=True)), handler)(True)
    host = _Host(_FakePet(ok=False))
    getattr(host, handler)(False)
    assert host._status.text() == _STALE


# ---- rig and script loading ------------------------------------------


def test_load_puppet_failure_reports_and_leaves_show(qapp):
    host = _Host(_FakePet(ok=False))
    assert host.load_puppet("a/rig.puppet") is False
    assert host._status.text() == "Failed to load a/rig.puppet"
    assert host._current_rig_label.text() == ""
    assert not host._show_check.isChecked()


@pytest.mark.parametrize("show", [True, False])
def test_load_puppet_success_names_the_rig(host, pet, show):
    assert host.load_puppet("a/rig.puppet", show=show) is True
    assert pet.calls == [("load_puppet_file", "a/rig.puppet")]
    assert host._current_rig_label.text() == "Loaded: rig.puppet"
    assert host._status.text() == ""
    assert host._show_check.isChecked() is show


def test_open_example_reports_a_missing_rig(host, pet, monkeypatch, tmp_path):
    from Imervue.system import app_paths

    monkeypatch.setattr(app_paths, "examples_dir", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    host._on_open_example()
    assert pet.calls == []
    assert host._status.text().startswith("Bundled example not found at examples/puppet/")


def test_open_example_loads_the_bundled_rig(host, pet, monkeypatch, tmp_path):
    from Imervue.system import app_paths

    rig = tmp_path / "puppet" / "imeru.puppet"
    rig.parent.mkdir()
    rig.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(app_paths, "examples_dir", lambda: tmp_path)
    host._on_open_example()
    assert pet.calls == [("load_puppet_file", rig)]


def test_script_label_defaults_and_names_the_file(host):
    assert host._format_script_label("") == "(Using built-in default voice)"
    assert host._format_script_label("d/voice.petscript.json") == "Loaded: voice.petscript.json"


def test_load_script_failure_and_success(qapp):
    failing = _Host(_FakePet(ok=False))
    assert failing.load_script("x.json") is False
    assert failing._status.text() == "Failed to load script: x.json"
    pet = _FakePet()
    ok = _Host(pet)
    assert ok.load_script("d/x.json") is True
    assert pet.calls == [("load_script_file", "d/x.json")]
    assert ok._current_script_label.text() == "Loaded: x.json"
    assert ok._status.text() == ""


@pytest.mark.parametrize("has_pet", [True, False])
def test_reset_script_forgets_the_path(qapp, has_pet):
    pet = _FakePet()
    host = _Host(pet if has_pet else None)
    pet_settings.update(script_path="old.json")
    host._on_reset_script()
    assert pet_settings.load()["script_path"] == ""
    assert host._current_script_label.text() == "(Using built-in default voice)"
    assert host._status.text() == ""
    assert pet.calls == ([("reset_script_to_default",)] if has_pet else [])


# ---- hotkeys -----------------------------------------------------------


def test_an_empty_hotkey_edit_is_ignored(host):
    edit = QKeySequenceEdit()
    host._on_hotkey_edited(ACTION_SPEAK_NOW, edit)
    assert host._status.text() == _STALE
    assert not pet_settings.load().get("hotkeys")


def test_a_saved_hotkey_restarts_a_running_listener(host, pet):
    pet.hotkeys_on = True
    edit = QKeySequenceEdit(QKeySequence("Ctrl+Alt+F8"))
    host._on_hotkey_edited(ACTION_SPEAK_NOW, edit)
    assert pet_settings.load()["hotkeys"][ACTION_SPEAK_NOW] == "Ctrl+Alt+F8"
    assert pet.calls == [("set_hotkeys_enabled", True)]
    assert host._status.text() == ""


def test_a_saved_hotkey_leaves_a_stopped_listener_alone(host, pet):
    edit = QKeySequenceEdit(QKeySequence("Ctrl+Alt+F7"))
    host._on_hotkey_edited(ACTION_SPEAK_NOW, edit)
    assert pet.calls == []


def test_a_taken_hotkey_is_put_back(host, pet):
    edit = QKeySequenceEdit(QKeySequence(DEFAULT_HOTKEY_BINDINGS[ACTION_TOGGLE_VISIBLE]))
    host._on_hotkey_edited(ACTION_SPEAK_NOW, edit)
    assert edit.keySequence().toString() == QKeySequence(
        DEFAULT_HOTKEY_BINDINGS[ACTION_SPEAK_NOW]).toString()
    assert "Show / hide pet" in host._status.text()
    assert pet.calls == []


# ---- lazy overlay and session restore --------------------------------


class _FakeOverlay(QObject):
    visibility_changed = Signal(bool)
    setting_changed = Signal(str, object)


def test_the_overlay_is_built_once_and_announced(qapp, monkeypatch):
    pet_settings.update(drivers={"auto_idle": False, "idle_motion": False, "auto_blink": True,
                                 "drag_track": False, "mouse_gaze": False, "mic_lipsync": True})
    monkeypatch.setattr(mod, "PetWindow", _FakeOverlay)
    seen, emitted = [], []
    host = SimpleNamespace(
        _pet_window=None,
        _on_pet_visibility_changed=lambda v: seen.append(("visible", v)),
        _on_pet_setting_changed=lambda k, v: seen.append((k, v)),
        pet_created=SimpleNamespace(emit=emitted.append),
    )
    window = PetWorkspace._ensure_pet_window(host)
    assert isinstance(window, _FakeOverlay)
    assert PetWorkspace._ensure_pet_window(host) is window
    assert emitted == [window]
    assert seen == [("drivers", {"auto_idle": False, "idle_motion": False, "auto_blink": True,
                                 "drag_track": False, "mouse_gaze": False})]
    window.visibility_changed.emit(True)
    window.setting_changed.emit("opacity", 0.5)
    assert seen[1:] == [("visible", True), ("opacity", 0.5)]


def test_reapply_ticks_only_saved_drivers(host):
    host._reapply_persisted_toggles({"drivers": {"mic_lipsync": True, "auto_idle": False}})
    assert host._mic_check.isChecked()
    assert not host._idle_check.isChecked()
    host._reapply_persisted_toggles({"drivers": None})


def _restoring_host(qapp, loaded: bool):
    host = _Host(_FakePet())
    host.loads = []

    def load_puppet(path, *, show=True):
        host.loads.append((path, show))
        return loaded
    host.load_puppet = load_puppet
    return host


def test_restore_skips_a_missing_rig_but_labels_the_script(qapp, tmp_path):
    pet_settings.update(last_rig_path=str(tmp_path / "gone.puppet"),
                        script_path="d/voice.json", show_on_launch=True)
    host = _restoring_host(qapp, True)
    host._restore_persisted_session()
    assert host.loads == []
    assert not host._show_check.isChecked()
    assert host._current_script_label.text() == "Loaded: voice.json"


@pytest.mark.parametrize(("loaded", "on_launch", "shown"), [
    (True, True, True), (True, False, False), (False, True, False),
])
def test_restore_reloads_the_rig_silently(qapp, tmp_path, loaded, on_launch, shown):
    rig = tmp_path / "r.puppet"
    rig.write_text("{}", encoding="utf-8")
    pet_settings.update(last_rig_path=str(rig), show_on_launch=on_launch,
                        drivers={"auto_blink": True})
    host = _restoring_host(qapp, loaded)
    host._restore_persisted_session()
    assert host.loads == [(str(rig), False)]
    assert host._show_check.isChecked() is shown
    assert host._blink_check.isChecked() is loaded
    assert host._current_script_label.text() == "(Using built-in default voice)"


def test_tray_and_pet_window_accessors(host, pet):
    tray = object()
    host.attach_tray(tray)
    assert host._tray is tray
    assert host.pet_window() is pet


# ---- the built tab ---------------------------------------------------


_DRIVER_HANDLERS = {
    "_idle_check": "_on_idle_toggled", "_idle_motion_check": "_on_idle_motion_toggled",
    "_blink_check": "_on_blink_toggled", "_drag_check": "_on_drag_toggled",
    "_gaze_check": "_on_gaze_toggled", "_mic_check": "_on_mic_toggled",
    "_webcam_check": "_on_webcam_toggled", "_hotkey_check": "_on_hotkeys_toggled",
}


def test_the_built_tab_wires_every_driver_and_orders_its_pages(qapp, monkeypatch):
    calls = []
    for handler in _DRIVER_HANDLERS.values():
        monkeypatch.setattr(PetWorkspace, handler,
                            lambda self, checked, _h=handler: calls.append((_h, checked)))
    ws = PetWorkspace()
    try:
        tabs = ws.findChild(QTabWidget, "petSettingsTabs")
        assert [tabs.tabText(i) for i in range(tabs.count())] == [
            "Window", "Live drivers", "Pet script", "Global hotkeys"]
        for attr, handler in _DRIVER_HANDLERS.items():
            getattr(ws, attr).setChecked(True)
            assert calls[-1] == (handler, True), attr
        assert sorted(ws._hotkey_edits) == sorted(DEFAULT_HOTKEY_BINDINGS)
        assert ws._current_script_label.text() == "(Using built-in default voice)"
        assert ws._current_rig_label.text() == "No rig loaded"
        assert ws.pet_window() is None
        assert isinstance(ws._size_combo, QComboBox)
    finally:
        ws.deleteLater()
