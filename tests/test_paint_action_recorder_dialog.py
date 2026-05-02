"""Qt smoke tests for the action-recorder dialog."""
from __future__ import annotations

import pytest

from Imervue.paint.action_recorder import (
    Action,
    ActionRecorder,
    ActionRecording,
    save_recordings,
)
from Imervue.paint.action_recorder_dialog import ActionRecorderDialog
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_persistence():
    user_setting_dict.pop("paint_action_recordings", None)
    yield
    user_setting_dict.pop("paint_action_recordings", None)


@pytest.fixture
def replay_log() -> list:
    return []


@pytest.fixture
def make_dialog(qapp, replay_log):
    """Factory: build a dialog with a fresh recorder + target."""
    holders: list[ActionRecorderDialog] = []

    def factory():
        recorder = ActionRecorder()
        target = lambda kind, params: replay_log.append((kind, dict(params)))  # noqa: E731
        dialog = ActionRecorderDialog(recorder, target)
        holders.append(dialog)
        return dialog, recorder

    yield factory

    for dialog in holders:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_dialog_starts_with_empty_recordings(make_dialog):
    dialog, _recorder = make_dialog()
    assert dialog.recordings() == []
    assert dialog._list.count() == 0   # noqa: SLF001


def test_dialog_loads_persisted_recordings(qapp, replay_log):
    save_recordings([
        ActionRecording(
            name="warmup",
            actions=[Action(kind="paint_row", params={"row": 1})],
        ),
    ])
    recorder = ActionRecorder()
    target = lambda kind, params: replay_log.append((kind, dict(params)))  # noqa: E731
    dialog = ActionRecorderDialog(recorder, target)
    try:
        assert len(dialog.recordings()) == 1
        assert dialog._list.count() == 1   # noqa: SLF001
    finally:
        dialog.deleteLater()


# ---------------------------------------------------------------------------
# Start / Stop wiring
# ---------------------------------------------------------------------------


def test_start_and_stop_button_state_follows_recorder(make_dialog):
    dialog, recorder = make_dialog()
    # Initially idle: Start enabled, Stop disabled.
    assert dialog._start_btn.isEnabled() is True   # noqa: SLF001
    assert dialog._stop_btn.isEnabled() is False   # noqa: SLF001
    recorder.start("manual")
    dialog._refresh_buttons()   # noqa: SLF001
    assert dialog._start_btn.isEnabled() is False   # noqa: SLF001
    assert dialog._stop_btn.isEnabled() is True   # noqa: SLF001


def test_stop_persists_recording_when_actions_were_captured(make_dialog):
    dialog, recorder = make_dialog()
    recorder.start("session")
    recorder.record("paint_row", {"row": 0})
    dialog._on_stop()   # noqa: SLF001
    assert len(dialog.recordings()) == 1
    raw = user_setting_dict["paint_action_recordings"]
    assert isinstance(raw, list) and len(raw) == 1


def test_stop_drops_empty_recording(make_dialog):
    dialog, recorder = make_dialog()
    recorder.start("session")   # no actions captured
    dialog._on_stop()   # noqa: SLF001
    assert dialog.recordings() == []


def test_stop_when_not_recording_is_no_op(make_dialog):
    dialog, _recorder = make_dialog()
    dialog._on_stop()   # noqa: SLF001
    assert dialog.recordings() == []


# ---------------------------------------------------------------------------
# Play
# ---------------------------------------------------------------------------


def test_play_replays_actions_to_target(make_dialog, replay_log):
    dialog, _recorder = make_dialog()
    dialog._recordings.append(   # noqa: SLF001
        ActionRecording(
            name="trace",
            actions=[
                Action(kind="paint_row", params={"row": 0}),
                Action(kind="paint_row", params={"row": 4}),
            ],
        ),
    )
    dialog._refresh_list()   # noqa: SLF001
    dialog._list.setCurrentRow(0)   # noqa: SLF001
    dialog._on_play()   # noqa: SLF001
    assert replay_log == [
        ("paint_row", {"row": 0}),
        ("paint_row", {"row": 4}),
    ]


def test_play_no_op_when_no_row_selected(make_dialog, replay_log):
    dialog, _recorder = make_dialog()
    dialog._recordings.append(   # noqa: SLF001
        ActionRecording(
            name="solo",
            actions=[Action(kind="paint_row", params={"row": 0})],
        ),
    )
    dialog._refresh_list()   # noqa: SLF001
    dialog._list.setCurrentRow(-1)   # noqa: SLF001
    dialog._on_play()   # noqa: SLF001
    assert replay_log == []


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_drops_selected_recording(make_dialog):
    dialog, _recorder = make_dialog()
    dialog._recordings.append(   # noqa: SLF001
        ActionRecording(
            name="r1",
            actions=[Action(kind="paint_row", params={"row": 0})],
        ),
    )
    dialog._refresh_list()   # noqa: SLF001
    dialog._list.setCurrentRow(0)   # noqa: SLF001
    dialog._on_delete()   # noqa: SLF001
    assert dialog.recordings() == []
    raw = user_setting_dict.get("paint_action_recordings", [])
    assert raw == []


def test_delete_no_op_when_no_row_selected(make_dialog):
    dialog, _recorder = make_dialog()
    dialog._recordings.append(   # noqa: SLF001
        ActionRecording(
            name="r1",
            actions=[Action(kind="paint_row", params={"row": 0})],
        ),
    )
    dialog._refresh_list()   # noqa: SLF001
    dialog._list.setCurrentRow(-1)   # noqa: SLF001
    dialog._on_delete()   # noqa: SLF001
    assert len(dialog.recordings()) == 1


# ---------------------------------------------------------------------------
# Status label
# ---------------------------------------------------------------------------


def test_status_text_changes_with_recording(make_dialog):
    dialog, recorder = make_dialog()
    idle_text = dialog._status.text()   # noqa: SLF001
    recorder.start("session")
    dialog._refresh_status()   # noqa: SLF001
    active_text = dialog._status.text()   # noqa: SLF001
    assert idle_text != active_text
