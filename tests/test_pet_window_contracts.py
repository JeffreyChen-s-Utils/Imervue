"""Contracts for the :class:`PetWindow` behaviour that lives outside its constructor.

``PetWindow`` builds a ``PuppetCanvas`` (a ``QOpenGLWidget``), so these tests
never instantiate it. Each one copies the methods under test onto a plain host
class and supplies only the attributes they read, which pins speech, script,
drop dispatch, motion playback, persistence, integrations, size presets and the
driver restore — plus the MRO guarantees the Qt event overrides rely on.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from Imervue.desktop_pet import pet_window
from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_script import PetScript
from Imervue.desktop_pet.pet_window import PetWindow


class _Recorder:
    """Callable that records each call's positional arguments."""

    def __init__(self, result=None) -> None:
        self.calls: list[tuple] = []
        self.result = result

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class _Signal:
    """Stand-in for a bound Qt signal: ``emit`` appends its arguments."""

    def __init__(self) -> None:
        self.emitted: list[tuple] = []

    def emit(self, *args) -> None:
        self.emitted.append(args)


class _Engine:
    """Script engine double whose pickers return preset lines."""

    def __init__(self, **lines) -> None:
        self.lines = lines
        self.scripts: list = []

    def _pick(self, name):
        return self.lines.get(name)

    def pick_for_hit_area(self, area):
        self.lines["seen_area"] = area
        return self._pick("hit")

    def pick_for_motion(self, name):
        return self._pick("motion")

    def pick_time_of_day_greeting(self):
        return self._pick("tod")

    def pick_greeting(self):
        return self._pick("greeting")

    def due_scheduled_message(self):
        return self._pick("scheduled")

    def set_script(self, script) -> None:
        self.scripts.append(script)


def _host(*names: str, **attrs):
    """A plain object carrying ``PetWindow``'s *names* plus *attrs*."""
    namespace = {name: PetWindow.__dict__.get(name, getattr(PetWindow, name)) for name in names}
    host = type("Host", (), namespace)()
    for key, value in attrs.items():
        setattr(host, key, value)
    return host


# ---------------------------------------------------------------
# Speech / script
# ---------------------------------------------------------------


def test_click_response_silent_when_speech_off():
    host = _host("speak_click_response", _speech_enabled=False, _show_speech=_Recorder())
    host.speak_click_response("head", "wave")
    assert host._show_speech.calls == []


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ({"hit": "H", "motion": "M", "tod": "T", "greeting": "G"}, "H"),
        ({"motion": "M", "tod": "T", "greeting": "G"}, "M"),
        ({"tod": "T", "greeting": "G"}, "T"),
        ({"greeting": "G"}, "G"),
    ],
)
def test_click_response_line_priority(lines, expected):
    host = _host(
        "speak_click_response", _speech_enabled=True, _script_engine=_Engine(**lines),
        _show_speech=_Recorder(), llm_dialogue_enabled=lambda: False,
    )
    host.speak_click_response("head", "wave")
    assert host._show_speech.calls == [(expected,)]


def test_click_response_empty_area_passes_none_and_skips_blank_line():
    engine = _Engine()
    host = _host(
        "speak_click_response", _speech_enabled=True, _script_engine=engine,
        _show_speech=_Recorder(), llm_dialogue_enabled=lambda: False,
    )
    host.speak_click_response("", None)
    assert engine.lines["seen_area"] is None
    assert host._show_speech.calls == []


def test_click_response_requests_llm_with_situation_tag():
    llm = SimpleNamespace(request_line=_Recorder())
    host = _host(
        "speak_click_response", _speech_enabled=True, _script_engine=_Engine(greeting="G"),
        _show_speech=_Recorder(), llm_dialogue_enabled=lambda: True, _llm=llm,
    )
    host.speak_click_response("", "wave")
    assert llm.request_line.calls == [("motion:wave",)]
    assert host._show_speech.calls == [("G",)]


def test_click_response_swallows_llm_value_error():
    def refuse(_tag):
        raise ValueError("no endpoint")

    host = _host(
        "speak_click_response", _speech_enabled=True, _script_engine=_Engine(),
        _show_speech=_Recorder(), llm_dialogue_enabled=lambda: True,
        _llm=SimpleNamespace(request_line=refuse),
    )
    host.speak_click_response("head", None)


def test_speak_and_speech_on_forward():
    host = _host("speak", "speech_on", _show_speech=_Recorder(), _speech_enabled=True)
    host.speak("hello")
    assert host._show_speech.calls == [("hello",)]
    assert host.speech_on is True


def test_set_speech_enabled_persists_and_closes_bubble():
    bubble = SimpleNamespace(close_bubble=_Recorder())
    host = _host("set_speech_enabled", "speech_enabled", _persist=_RecordingPersist(),
                 _speech=bubble)
    host.set_speech_enabled(0)
    assert host.speech_enabled() is False
    assert host._persist.fields == [{"speech_enabled": False}]
    assert bubble.close_bubble.calls == [()]
    host.set_speech_enabled(True)
    assert bubble.close_bubble.calls == [()]


def test_set_speech_disabled_without_bubble():
    host = _host("set_speech_enabled", _persist=_RecordingPersist(), _speech=None)
    host.set_speech_enabled(False)
    assert host._persist.fields == [{"speech_enabled": False}]


class _RecordingPersist:
    def __init__(self) -> None:
        self.fields: list[dict] = []

    def __call__(self, **fields) -> None:
        self.fields.append(fields)


@pytest.mark.parametrize(
    ("enabled", "text", "visible"),
    [(False, "hi", True), (True, "", True), (True, "hi", False)],
)
def test_show_speech_gates(enabled, text, visible):
    host = _host("_show_speech", _speech_enabled=enabled, _speech=None,
                 isVisible=lambda: visible)
    host._show_speech(text)
    assert host._speech is None


def test_show_speech_reuses_existing_bubble():
    bubble = SimpleNamespace(anchor_to=_Recorder(), show_message=_Recorder())
    host = _host("_show_speech", _speech_enabled=True, _speech=bubble,
                 isVisible=lambda: True, geometry=lambda: "geom")
    host._show_speech("hi")
    assert bubble.anchor_to.calls == [("geom",)]
    assert bubble.show_message.calls == [("hi",)]


def test_show_speech_creates_bubble(qapp):
    host = _host("_show_speech", _speech_enabled=True, _speech=None,
                 isVisible=lambda: True, geometry=lambda: QRect(0, 0, 10, 10))
    host._show_speech("hi")
    try:
        assert host._speech is not None
    finally:
        host._speech.close_bubble()
        host._speech.deleteLater()


def test_reanchor_speech_only_with_bubble():
    host = _host("reanchor_speech", _speech=None)
    host.reanchor_speech()
    bubble = SimpleNamespace(anchor_to=_Recorder())
    host = _host("reanchor_speech", _speech=bubble, geometry=lambda: "g")
    host.reanchor_speech()
    assert bubble.anchor_to.calls == [("g",)]


def _write_script(path: Path) -> Path:
    path.write_text(json.dumps({"greetings": ["yo"]}), encoding="utf-8")
    return path


def test_load_script_file_success(tmp_path):
    engine = _Engine()
    host = _host("load_script_file", _script_engine=engine, _persist=_RecordingPersist())
    path = _write_script(tmp_path / "a.petscript.json")
    assert host.load_script_file(path) is True
    assert len(engine.scripts) == 1
    assert host._persist.fields == [{"script_path": str(path)}]


def test_load_script_file_failure_logs(tmp_path, caplog):
    engine = _Engine()
    host = _host("load_script_file", _script_engine=engine, _persist=_RecordingPersist())
    with caplog.at_level("WARNING", logger="Imervue.desktop_pet.pet_window"):
        assert host.load_script_file(tmp_path / "missing.json") is False
    assert engine.scripts == []
    assert host._persist.fields == []
    assert "pet script" in caplog.text


def test_reset_script_to_default_and_engine_accessor():
    engine = _Engine()
    host = _host("reset_script_to_default", "script_engine", _script_engine=engine,
                 _persist=_RecordingPersist())
    host.reset_script_to_default()
    assert isinstance(engine.scripts[0], PetScript)
    assert host._persist.fields == [{"script_path": ""}]
    assert host.script_engine() is engine


def test_restore_persisted_script_paths(tmp_path, caplog):
    engine = _Engine()
    host = _host("_restore_persisted_script", _script_engine=engine,
                 _settings={"script_path": None})
    host._restore_persisted_script()
    assert engine.scripts == []
    host._settings = {"script_path": str(tmp_path / "gone.json")}
    with caplog.at_level("INFO", logger="Imervue.desktop_pet.pet_window"):
        host._restore_persisted_script()
    assert engine.scripts == []
    assert "stale pet script" in caplog.text
    host._settings = {"script_path": str(_write_script(tmp_path / "ok.json"))}
    host._restore_persisted_script()
    assert len(engine.scripts) == 1


@pytest.mark.parametrize(
    ("enabled", "line", "expected"),
    [(False, "x", []), (True, None, []), (True, "chime", [("chime",)])],
)
def test_on_script_tick(enabled, line, expected):
    host = _host("_on_script_tick", _speech_enabled=enabled,
                 _script_engine=_Engine(scheduled=line), _show_speech=_Recorder())
    host._on_script_tick()
    assert host._show_speech.calls == expected


# ---------------------------------------------------------------
# Drops, motions and expressions
# ---------------------------------------------------------------


def _drop_host(speech: bool, engine: _Engine):
    return _host(
        "handle_dropped_paths", load_puppet_file=_Recorder(True), hit_triggered=_Signal(),
        play_random_motion_in_group=_Recorder(True), _speech_enabled=speech,
        _script_engine=engine, _show_speech=_Recorder(),
    )


def test_drop_puppet_loads_and_emits():
    host = _drop_host(True, _Engine())
    rig = Path("rig.puppet")
    assert host.handle_dropped_paths([Path("a.png"), rig]) == "puppet"
    assert host.load_puppet_file.calls == [(rig,)]
    assert host.hit_triggered.emitted == [("",)]
    assert host.play_random_motion_in_group.calls == []


def test_drop_other_plays_group_and_greets():
    host = _drop_host(True, _Engine(tod=None, greeting="G"))
    assert host.handle_dropped_paths([Path("a.png")]) == "other"
    assert host.play_random_motion_in_group.calls == [(pet_window.DROP_MOTION_GROUP,)]
    assert host._show_speech.calls == [("G",)]


def test_drop_other_without_speech_or_line():
    host = _drop_host(False, _Engine(greeting="G"))
    host.handle_dropped_paths([Path("a.png")])
    assert host._show_speech.calls == []
    host = _drop_host(True, _Engine())
    host.handle_dropped_paths([Path("a.png")])
    assert host._show_speech.calls == []


def test_drop_none_is_noop():
    host = _drop_host(True, _Engine(greeting="G"))
    assert host.handle_dropped_paths([]) == "none"
    assert host.load_puppet_file.calls == []
    assert host.play_random_motion_in_group.calls == []


class _Url:
    def __init__(self, local: str, is_local: bool = True) -> None:
        self._local = local
        self._is_local = is_local

    def isLocalFile(self) -> bool:  # noqa: N802 - mirrors QUrl
        return self._is_local

    def toLocalFile(self) -> str:  # noqa: N802 - mirrors QUrl
        return self._local


class _DropEvent:
    def __init__(self, urls) -> None:
        self._urls = urls
        self.result: list[str] = []

    def mimeData(self):  # noqa: N802 - mirrors QDropEvent
        return SimpleNamespace(hasUrls=lambda: self._urls is not None, urls=lambda: self._urls)

    def acceptProposedAction(self) -> None:  # noqa: N802 - mirrors QDropEvent
        self.result.append("accept")

    def ignore(self) -> None:
        self.result.append("ignore")


def test_drag_enter_accepts_only_urls():
    host = _host("dragEnterEvent")
    with_urls, without = _DropEvent([]), _DropEvent(None)
    host.dragEnterEvent(with_urls)
    host.dragEnterEvent(without)
    assert with_urls.result == ["accept"]
    assert without.result == ["ignore"]


def test_drop_event_filters_urls():
    host = _host("dropEvent", handle_dropped_paths=_Recorder("other"))
    event = _DropEvent([_Url("C:/a.png"), _Url("", True), _Url("http://x", False)])
    host.dropEvent(event)
    assert host.handle_dropped_paths.calls == [([Path("C:/a.png")],)]
    assert event.result == ["accept"]
    rejected = _DropEvent(None)
    host.dropEvent(rejected)
    assert rejected.result == ["ignore"]
    assert len(host.handle_dropped_paths.calls) == 1


class _Player:
    def __init__(self, current=None) -> None:
        self.current = current
        self.played: list = []

    def motion(self):
        return self.current

    def set_motion(self, motion) -> None:
        self.current = motion

    def play(self) -> None:
        self.played.append(self.current)


def _motion(name: str, group: str = "Drop"):
    return SimpleNamespace(name=name, group=group)


def _play_host(motions, current=None):
    return _host(
        "play_random_motion_in_group", "_play_motion", "play_motion", "play_group",
        "_play_motion_by_name", _motion_player=_Player(current),
        document=lambda: None if motions is None else SimpleNamespace(motions=motions),
    )


def test_play_random_motion_excludes_previous():
    a, b = _motion("a"), _motion("b")
    host = _play_host([a, b], current=a)
    assert host.play_random_motion_in_group("Drop") is True
    assert host._motion_player.played == [b]


def test_play_random_motion_without_match():
    host = _play_host([_motion("a", "Idle")])
    assert host.play_random_motion_in_group("Drop") is False
    assert host.play_group("Drop") is False
    assert _play_host(None).play_random_motion_in_group("Drop") is False


def test_play_motion_by_name_and_public_alias():
    a, b = _motion("a"), _motion("b")
    host = _play_host([a, b])
    host._play_motion_by_name("b")
    host._play_motion_by_name("zzz")
    host.play_motion(a)
    assert host._motion_player.played == [b, a]
    _play_host(None)._play_motion_by_name("a")


def test_apply_expression_toggles():
    active: list[str] = ["smile"]
    canvas = SimpleNamespace(
        active_expressions=lambda: list(active),
        remove_expression=active.remove, add_expression=active.append,
    )
    host = _host("apply_expression", "_apply_expression", _canvas=canvas)
    host.apply_expression("smile")
    assert active == []
    host.apply_expression("angry")
    assert active == ["angry"]


# ---------------------------------------------------------------
# Persistence, FeatureHost adapter and integrations
# ---------------------------------------------------------------


def test_persist_writes_own_slot_and_emits(monkeypatch):
    writes: list = []
    monkeypatch.setattr(pet_settings, "update", lambda pid, **f: writes.append((pid, f)))
    host = _host("_persist", "persist", "persist_driver", "_persist_driver", "setting",
                 "pet_id", _pet_id="p2", setting_changed=_Signal(),
                 _settings={"drivers": {"auto_blink": True}})
    host.persist(a=1, b=2)
    assert writes == [("p2", {"a": 1, "b": 2})]
    assert host.setting_changed.emitted == [("a", 1), ("b", 2)]
    host.persist_driver("mouse_gaze", 1)
    assert host._settings["drivers"] == {"auto_blink": True, "mouse_gaze": True}
    assert writes[-1] == ("p2", {"drivers": {"auto_blink": True, "mouse_gaze": True}})
    assert host.setting("missing", 7) == 7
    assert host.pet_id() == "p2"


def test_set_idle_motion_enabled_uses_pet_cycle():
    drivers = SimpleNamespace(set_idle_motion_enabled=_Recorder())
    host = _host("set_idle_motion_enabled", _canvas_drivers=drivers,
                 _persist_driver=_Recorder())
    host.set_idle_motion_enabled(1)
    assert drivers.set_idle_motion_enabled.calls == [(True, pet_window.PET_IDLE_CYCLE_DURATION_S)]
    assert host._persist_driver.calls == [("idle_motion", True)]


def test_on_hotkey_action_forwards():
    host = _host("on_hotkey_action", _on_hotkey_action=_Recorder())
    host.on_hotkey_action("speak")
    assert host._on_hotkey_action.calls == [("speak",)]


def test_integrations_replace_and_remove(caplog):
    old = SimpleNamespace(shutdown=_Recorder())

    def broken():
        raise RuntimeError("boom")

    host = _host("add_integration", "remove_integration", "integration",
                 _features={"x": old})
    new = SimpleNamespace(shutdown=broken)
    host.add_integration("x", new)
    assert old.shutdown.calls == [()]
    assert host.integration("x") is new
    with caplog.at_level("WARNING"):
        host.remove_integration("x")
    assert host.integration("x") is None
    host.remove_integration("never")


def test_shutdown_continues_past_failures():
    order: list[str] = []

    def failing():
        order.append("feature")
        raise RuntimeError("x")

    host = _host(
        "shutdown",
        _features={"a": SimpleNamespace(shutdown=failing)},
        _music_rhythm=SimpleNamespace(shutdown=lambda: order.append("music")),
        _canvas_drivers=SimpleNamespace(shutdown=lambda: order.append("drivers")),
        _llm=SimpleNamespace(shutdown=lambda: order.append("llm")),
    )
    host.shutdown()
    assert order == ["feature", "music", "drivers", "llm"]


_DRIVER_SETTERS = (
    ("auto_idle", "set_auto_idle_enabled"),
    ("idle_motion", "set_idle_motion_enabled"),
    ("auto_blink", "set_auto_blink_enabled"),
    ("drag_track", "set_drag_track_enabled"),
    ("mouse_gaze", "set_mouse_gaze_enabled"),
    ("music_rhythm", "set_music_rhythm_enabled"),
    ("idle_minigame", "set_idle_minigame_enabled"),
)


def _order_setter(order: list, name: str):
    return lambda on: order.append((name, on))


def _restore_host(drivers):
    order: list[str] = []
    attrs = {setter: _order_setter(order, setter) for _key, setter in _DRIVER_SETTERS}
    host = _host("_restore_drivers", _settings={"drivers": drivers}, **attrs)
    return host, order


def test_restore_drivers_wakes_persisted_in_order():
    host, order = _restore_host({key: True for key, _setter in reversed(_DRIVER_SETTERS)}
                                | {"webcam_tracking": True, "mic_lipsync": True})
    host._restore_drivers()
    assert order == [(setter, True) for _key, setter in _DRIVER_SETTERS]


@pytest.mark.parametrize("drivers", [None, [], "x", {}, {"auto_idle": False}])
def test_restore_drivers_ignores_empty_or_malformed(drivers):
    host, order = _restore_host(drivers)
    host._restore_drivers()
    assert order == []


# ---------------------------------------------------------------
# Menu rows and size presets
# ---------------------------------------------------------------


def test_menu_rows_report_live_state():
    drivers = SimpleNamespace(
        idle_running=lambda: True, idle_motion_running=lambda: False,
        gaze_running=lambda: True, webcam_running=lambda: False,
    )
    engine = SimpleNamespace(blink_enabled=lambda: True, drag_enabled=lambda: False,
                             lipsync_enabled=lambda: True)
    setters = [setter for _key, setter in _DRIVER_SETTERS] + [
        "set_mic_lipsync_enabled", "set_webcam_tracking_enabled", "set_anchor_locked",
        "set_click_through", "set_always_on_bottom", "set_hide_on_fullscreen",
        "set_speech_enabled",
    ]
    host = _host("driver_menu_entries", "toggle_menu_entries", *setters,
                 _canvas_drivers=drivers, _input_engine=engine,
                 _anchor_locked=True, _click_through=False, _always_on_bottom=True,
                 _hide_on_fullscreen=False, _speech_enabled=True)
    rows = host.driver_menu_entries()
    assert [r[0] for r in rows] == [
        "desktop_pet_auto_idle", "desktop_pet_idle_motion", "desktop_pet_auto_blink",
        "desktop_pet_drag_track", "desktop_pet_mouse_gaze", "desktop_pet_mic_lipsync",
        "desktop_pet_webcam",
    ]
    assert [r[2] for r in rows] == [True, False, True, False, True, True, False]
    assert [r[3].__name__ for r in rows] == [
        "set_auto_idle_enabled", "set_idle_motion_enabled", "set_auto_blink_enabled",
        "set_drag_track_enabled", "set_mouse_gaze_enabled", "set_mic_lipsync_enabled",
        "set_webcam_tracking_enabled",
    ]
    toggles = host.toggle_menu_entries()
    assert [r[0] for r in toggles] == [
        "desktop_pet_anchor", "desktop_pet_click_through", "desktop_pet_on_bottom",
        "desktop_pet_hide_fullscreen", "desktop_pet_speech",
    ]
    assert [r[2] for r in toggles] == [True, False, True, False, True]
    assert [r[3].__name__ for r in toggles] == [
        "set_anchor_locked", "set_click_through", "set_always_on_bottom",
        "set_hide_on_fullscreen", "set_speech_enabled",
    ]


@pytest.mark.parametrize(
    ("size", "expected"),
    [((200, 300), "small"), ((480, 720), "large"), ((321, 480), "medium")],
)
def test_current_size_preset(size, expected):
    host = _host("_current_size_preset", "current_size_preset",
                 width=lambda: size[0], height=lambda: size[1])
    assert host.current_size_preset() == expected


def test_set_size_preset_unknown_is_noop():
    host = _host("set_size_preset", _persist=_RecordingPersist())
    host.set_size_preset("huge")
    assert host._persist.fields == []


def test_set_size_preset_keeps_centre_and_snaps(qapp):
    widget = QWidget()
    widget.setGeometry(100, 100, 320, 480)
    centre = widget.geometry().center()
    snaps: list[int] = []
    host = _host(
        "set_size_preset", _persist=_RecordingPersist(), geometry=widget.geometry,
        resize=widget.resize, setGeometry=widget.setGeometry,
        _apply_edge_snap=lambda: snaps.append(1),
    )
    try:
        host.set_size_preset("small")
        assert (widget.width(), widget.height()) == pet_window.SIZE_PRESETS["small"]
        assert abs(widget.geometry().center().x() - centre.x()) <= 1
        assert snaps == [1]
        assert host._persist.fields == [{"size_preset": "small"}]
    finally:
        widget.deleteLater()


# ---------------------------------------------------------------
# Public surface and MRO
# ---------------------------------------------------------------


def test_public_names_still_import_from_pet_window():
    for name in ("DEFAULT_PET_SIZE", "SIZE_PRESETS", "PAINT_TICK_INTERVAL_MS",
                 "SCRIPT_TICK_INTERVAL_MS", "PET_IDLE_CYCLE_DURATION_S",
                 "DRAG_MOTION_GROUP", "LAND_MOTION_GROUP", "DROP_MOTION_GROUP",
                 "PUPPET_FILE_SUFFIX", "DEFAULT_GREETINGS", "classify_drop_paths",
                 "PetWindow"):
        assert hasattr(pet_window, name), name
    assert pet_window.SIZE_PRESETS["medium"] == pet_window.DEFAULT_PET_SIZE


@pytest.mark.parametrize(
    "name", ["dragEnterEvent", "dropEvent", "showEvent", "hideEvent", "eventFilter"],
)
def test_qt_overrides_resolve_ahead_of_qwidget(name):
    owner = next(k for k in PetWindow.__mro__ if name in k.__dict__)
    assert owner is not QWidget
    assert PetWindow.__mro__.index(owner) < PetWindow.__mro__.index(QWidget)
