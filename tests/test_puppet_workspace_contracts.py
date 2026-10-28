"""Workspace action contracts without constructing widgets or opening devices."""
from types import MethodType, SimpleNamespace

import pytest

from Imervue.puppet.workspace import PuppetWorkspace


class Host(SimpleNamespace):
    def __getattr__(self, name):
        return MethodType(getattr(PuppetWorkspace, name), self)


def host_for(doc):
    calls = []
    host = Host(
        _canvas=SimpleNamespace(
            document=lambda: doc,
            load_document=lambda value: calls.append(("load", value)),
            parameter_values=lambda: {"P": 0.25},
            set_parameter_value=lambda *args: calls.append(("parameter", *args)),
        ),
        _announce=lambda key, fallback, **values: calls.append((key, values)),
        _status_label=SimpleNamespace(setText=lambda text: calls.append(("status", text))),
    )
    return host, calls


def patch_global(monkeypatch, method, name, value):
    monkeypatch.setitem(getattr(PuppetWorkspace, method).__globals__, name, value)


@pytest.mark.parametrize("kind,prefix,namespace", [
    ("rotation_deformer", "rotation_", "deformers"),
    ("warp_deformer", "warp_", "deformers"),
    ("parameter", "Param", "parameters"),
])
@pytest.mark.parametrize("outcome", [True, False, None])
def test_authoring_order_and_first_available_id(monkeypatch, kind, prefix, namespace, outcome):
    doc = SimpleNamespace(deformers=[], parameters=[])
    setattr(doc, namespace, [SimpleNamespace(id=prefix + suffix) for suffix in ("1", "3")])
    host, calls = host_for(None if outcome is None else doc)

    def create(document, identifier):
        assert document is doc
        calls.append(("create", identifier))
        return outcome

    patch_global(monkeypatch, "_add_" + kind, "add_" + kind, create)
    getattr(host, "_add_" + kind)()
    if outcome is None:
        assert calls == []
    elif outcome:
        key = "puppet_added_parameter" if kind == "parameter" else "puppet_added_deformer"
        assert calls == [("create", prefix + "2"), ("load", doc), (key, {"id": prefix + "2"})]
    else:
        assert calls == [("create", prefix + "2")]


@pytest.mark.parametrize("method", ["set_key_at_current_slider", "remove_key_at_current_slider"])
@pytest.mark.parametrize("outcome", [True, False, "missing", "no_document"])
def test_key_edit_post_success_order(monkeypatch, method, outcome):
    doc = object()
    host, calls = host_for(None if outcome == "no_document" else doc)
    forms = object()
    if method.startswith("set"):
        patch_global(monkeypatch, method, "snapshot_current_forms", lambda d: forms)

        def edit(document, key, value, snapshot):
            assert snapshot is forms
            calls.append(("edit", key, value))
            return outcome

        patch_global(monkeypatch, method, "set_key_at_value", edit)
    else:
        def edit(document, key, value):
            calls.append(("edit", key, value))
            return outcome

        patch_global(monkeypatch, method, "remove_key", edit)
    result = getattr(host, method)("missing" if outcome == "missing" else "P")
    if outcome in {"missing", "no_document"}:
        assert result is False
        assert calls == []
    elif outcome is False:
        assert result is False
        assert calls == [("edit", "P", 0.25)]
    else:
        assert result is True
        expected = [("edit", "P", 0.25)]
        if method.startswith("remove"):
            expected += [("load", doc), ("parameter", "P", 0.25)]
        key = "puppet_key_set" if method.startswith("set") else "puppet_key_removed"
        assert calls == expected + [(key, {"id": "P", "value": 0.25})]


@pytest.mark.parametrize("failure", [None, FileNotFoundError, ValueError])
def test_open_result_and_failure_boundary(monkeypatch, failure):
    doc = SimpleNamespace(size=(40, 50), drawables=[object()])
    host, calls = host_for(None)

    def load(path):
        calls.append(("read", path))
        if failure:
            raise failure("bad file")
        return doc

    patch_global(monkeypatch, "open_puppet", "load_puppet", load)
    patch_global(monkeypatch, "open_puppet", "_push_recent", lambda path: calls.append(("recent", path)))
    if failure is ValueError:
        with pytest.raises(ValueError, match="bad file"):
            host.open_puppet("folder/test.puppet")
        assert calls == [("read", "folder/test.puppet")]
    else:
        assert host.open_puppet("folder/test.puppet") is (failure is None)
        if failure is None:
            assert [call[0] for call in calls] == ["read", "load", "status", "recent"]
        else:
            assert [call[0] for call in calls] == ["read", "status"]


@pytest.mark.parametrize("outcome", ["success", "missing", "io_error", "other_error"])
def test_save_result_suffix_and_recent_order(monkeypatch, outcome):
    doc = object()
    host, calls = host_for(None if outcome == "missing" else doc)

    def save(document, path):
        assert document is doc
        calls.append(("write", path))
        if outcome == "io_error":
            raise OSError("write failed")
        if outcome == "other_error":
            raise ValueError("bad document")

    patch_global(monkeypatch, "save_puppet", "save_puppet", save)
    patch_global(monkeypatch, "save_puppet", "_push_recent", lambda path: calls.append(("recent", path)))
    if outcome == "other_error":
        with pytest.raises(ValueError, match="bad document"):
            host.save_puppet("no_suffix")
    else:
        assert host.save_puppet("no_suffix") is (outcome == "success")
    assert [c[0] for c in calls] == {
        "success": ["write", "status", "recent"], "missing": [],
        "io_error": ["write", "status"], "other_error": ["write"],
    }[outcome]
    if calls:
        assert calls[0] == ("write", "no_suffix")


@pytest.mark.parametrize("enabled,missing,opened", [
    (False, True, False), (True, True, False), (True, False, False), (True, False, True),
])
def test_lipsync_prerequisite_and_toggle_order(monkeypatch, enabled, missing, opened):
    host, calls = host_for(None)
    host._lipsync_toggle = SimpleNamespace(
        blockSignals=lambda value: calls.append(("block", value)),
        setChecked=lambda value: calls.append(("checked", value)),
    )
    host._prompt_install = lambda packages, on_ready: calls.append(("install", on_ready))
    host._input_engine = SimpleNamespace(
        set_lipsync_enabled=lambda value: calls.append(("input", value)) or opened,
    )
    patch_global(monkeypatch, "_toggle_lipsync", "missing_packages", lambda p: missing)
    host._toggle_lipsync(enabled)
    if enabled and missing:
        assert [c[0] for c in calls] == ["install", "block", "checked", "block"]
        calls[0][1]()
        assert calls[-1] == ("checked", True)
    elif enabled and not opened:
        assert [c[0] for c in calls] == ["input", "block", "checked", "block",
                                       "puppet_lipsync_unavailable"]
    else:
        assert calls == [("input", enabled)]


@pytest.mark.parametrize("enabled,started", [(False, False), (True, False), (True, True)])
def test_motion_record_toggle_failure_blocks_callback(enabled, started):
    host, calls = host_for(None)
    host._start_motion_recording = lambda: calls.append(("start",)) or started
    host._motion_recorder = SimpleNamespace(stop=lambda: calls.append(("stop",)))
    host._motion_record_toggle = SimpleNamespace(
        blockSignals=lambda value: calls.append(("block", value)),
        setChecked=lambda value: calls.append(("checked", value)),
    )
    host._toggle_motion_record(enabled)
    expected = [("start",)] if enabled else [("stop",)]
    if enabled and not started:
        expected += [("block", True), ("checked", False), ("block", False)]
    assert calls == expected


@pytest.mark.parametrize("method", ["_add_rotation_deformer", "_add_warp_deformer", "_add_parameter"])
def test_empty_document_skips_identifier_lookup(method):
    host = SimpleNamespace(_canvas=SimpleNamespace(document=lambda: None))
    getattr(PuppetWorkspace, method)(host)


@pytest.mark.parametrize("playing,fading", [(False, False), (True, False), (False, True)])
def test_reset_stops_producers_before_restoring_state(playing, fading):
    doc = SimpleNamespace(pose_groups=[
        SimpleNamespace(id="visible", drawables=["first", "second"]),
        SimpleNamespace(id="empty", drawables=[]),
    ])
    host, calls = host_for(doc)
    player = SimpleNamespace(
        is_playing=lambda: playing, is_fading_out=lambda: fading,
        _snap_stop=lambda: calls.append("stop"),
    )
    host._motion_dock = SimpleNamespace(player=lambda: player)
    host._drag_toggle = SimpleNamespace(
        isChecked=lambda: True, setChecked=lambda value: calls.append(("drag", value)),
    )
    host._blink_toggle = SimpleNamespace(isChecked=lambda: False)
    host._canvas.active_expressions = lambda: ["happy", "sad"]
    host._canvas.remove_expression = lambda name: calls.append(("expression", name))
    host._canvas.set_pose_active = lambda *args: calls.append(("pose", *args))
    host._canvas.reset_physics = lambda: calls.append("physics")
    host._canvas.reset_parameters = lambda: calls.append("parameters")
    host._status = SimpleNamespace(setText=lambda text: calls.append("status"))
    host_type = type("ResetHost", (), {})
    reset_host = host_type()
    reset_host.__dict__.update(host.__dict__)
    PuppetWorkspace._reset_to_rest(reset_host)
    expected = ["stop"] if playing or fading else []
    assert calls == expected + [("drag", False), ("expression", "happy"),
                                ("expression", "sad"), ("pose", "visible", "first"),
                                "physics", "parameters", "status"]


@pytest.mark.parametrize("choice", ["", "save", "UPPER.PUPPET"])
def test_save_dialog_alone_appends_file_suffix(monkeypatch, choice):
    host, calls = host_for(object())
    host.save_puppet = lambda path: calls.append(path)
    owner = PuppetWorkspace._save_via_dialog.__globals__
    monkeypatch.setattr(owner["QFileDialog"], "getSaveFileName", lambda *a: (choice, ""))
    host._save_via_dialog()
    assert calls == ([] if not choice else [choice if "." in choice else "save.puppet"])


@pytest.mark.parametrize("active", [False, True])
def test_timeline_commit_reuses_current_time(active):
    host, calls = host_for(None)
    player = SimpleNamespace(motion=lambda: object() if active else None,
                             elapsed=lambda: 2.75, seek=calls.append)
    host._motion_dock = SimpleNamespace(player=lambda: player)
    host._on_timeline_edit_committed()
    assert calls == ([2.75] if active else [])
