"""Qt dialog wrapping the action-recorder engine.

The recorder data layer ships in :mod:`Imervue.paint.action_recorder`;
this module is the user-facing UI: a small QDialog that lists saved
recordings, lets the user start / stop a new recording, replay or
delete a selected one, and round-trips the registry through the
persistence helpers.

The dialog stays decoupled from the workspace by accepting:

* A live :class:`ActionRecorder` instance (provided by the workspace
  so a dispatcher recording in progress is visible in the dialog).
* A ``target`` callable matching the ``replay`` signature so the
  Play button hands captured ``(kind, params)`` events back to the
  same dispatcher entry points the recorder originally tapped.

Construction is cheap; the dialog reads the persisted registry on
init and writes it back whenever a recording is added or removed.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.action_recorder import (
    ActionRecorder,
    ActionRecording,
    load_recordings,
    replay,
    save_recordings,
)


class ActionRecorderDialog(QDialog):
    """Modal control panel for the action-recorder engine."""

    def __init__(
        self,
        recorder: ActionRecorder,
        target: Callable[[str, dict], None],
        parent=None,
    ):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            lang.get("paint_action_recorder", "Action Recorder"),
        )
        self.setMinimumWidth(420)
        self._recorder = recorder
        self._target = target
        self._recordings: list[ActionRecording] = load_recordings()

        self._list = QListWidget()
        self._list.currentRowChanged.connect(
            lambda _row: self._refresh_buttons(),
        )
        self._refresh_list()

        self._status = QLabel()
        self._refresh_status()

        self._start_btn = QPushButton(
            lang.get("paint_action_recorder_start", "Start"),
        )
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn = QPushButton(
            lang.get("paint_action_recorder_stop", "Stop"),
        )
        self._stop_btn.clicked.connect(self._on_stop)
        self._play_btn = QPushButton(
            lang.get("paint_action_recorder_play", "Play"),
        )
        self._play_btn.clicked.connect(self._on_play)
        self._delete_btn = QPushButton(
            lang.get("paint_action_recorder_delete", "Delete"),
        )
        self._delete_btn.clicked.connect(self._on_delete)

        controls = QHBoxLayout()
        controls.addWidget(self._start_btn)
        controls.addWidget(self._stop_btn)
        controls.addWidget(self._play_btn)
        controls.addWidget(self._delete_btn)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            lang.get("paint_action_recorder_recordings", "Recordings:"),
        ))
        layout.addWidget(self._list, stretch=1)
        layout.addLayout(controls)
        layout.addWidget(self._status)
        close_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            Qt.Orientation.Horizontal, self,
        )
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

        self._refresh_buttons()

    # ---- public API ------------------------------------------------------

    def recordings(self) -> list[ActionRecording]:
        """Return the dialog's currently-known recording list."""
        return list(self._recordings)

    # ---- slots -----------------------------------------------------------

    def _on_start(self) -> None:
        if self._recorder.is_recording:
            return
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("paint_action_recorder", "Action Recorder"),
            lang.get("paint_action_recorder_name", "Recording name:"),
        )
        if not ok:
            return
        cleaned = name.strip()
        if not cleaned:
            return
        self._recorder.start(cleaned)
        self._refresh_status()
        self._refresh_buttons()

    def _on_stop(self) -> None:
        if not self._recorder.is_recording:
            return
        recording = self._recorder.stop()
        if recording is not None and recording.actions:
            self._recordings.append(recording)
            save_recordings(self._recordings)
            self._refresh_list()
        self._refresh_status()
        self._refresh_buttons()

    def _on_play(self) -> None:
        index = self._list.currentRow()
        if not 0 <= index < len(self._recordings):
            return
        replay(self._recordings[index], self._target)

    def _on_delete(self) -> None:
        index = self._list.currentRow()
        if not 0 <= index < len(self._recordings):
            return
        del self._recordings[index]
        save_recordings(self._recordings)
        self._refresh_list()
        self._refresh_buttons()

    # ---- internals -------------------------------------------------------

    def _refresh_list(self) -> None:
        self._list.clear()
        for recording in self._recordings:
            item = QListWidgetItem(
                f"{recording.name}  ({len(recording.actions)})",
            )
            self._list.addItem(item)

    def _refresh_status(self) -> None:
        lang = language_wrapper.language_word_dict
        if self._recorder.is_recording:
            self._status.setText(
                lang.get(
                    "paint_action_recorder_status_active",
                    "Recording in progress…",
                ),
            )
        else:
            self._status.setText(
                lang.get("paint_action_recorder_status_idle", "Idle"),
            )

    def _refresh_buttons(self) -> None:
        recording = self._recorder.is_recording
        self._start_btn.setEnabled(not recording)
        self._stop_btn.setEnabled(recording)
        has_selection = self._list.currentRow() >= 0
        self._play_btn.setEnabled(has_selection and not recording)
        self._delete_btn.setEnabled(has_selection and not recording)
