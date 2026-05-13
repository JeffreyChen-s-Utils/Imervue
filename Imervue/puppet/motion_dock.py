"""Bottom-docked motion playback panel.

Lists the motions in the active document, lets the user pick one,
and drives a :class:`MotionPlayer` via Play / Pause / Stop / Loop
controls. A scrub slider shows current playhead position and lets
the user seek.

Read-only for Phase 6 — motion editing UI (timeline keyframe drag /
segment-type swap) follows in a later phase.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.motion_player import MotionPlayer

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas


_SCRUB_STEPS: int = 1000


class MotionDock(QDockWidget):
    """Lists motions on the current document and drives a MotionPlayer."""

    motion_picked = Signal(str)

    def __init__(self, canvas: PuppetCanvas, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("puppet_motions_dock", "Motions"), parent)
        self._canvas = canvas
        self._player = MotionPlayer(canvas, self)
        self._inner = QWidget()
        layout = QVBoxLayout(self._inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._list = QListWidget()
        # Single-click binds the motion to the player and starts playback
        # right away — the most-asked-for UX in animation tools, matches
        # raster paint apps's brush-preset list / other XMP-aware photo managers's preset preview /
        # most DAWs. Double-click is harmless because binding +
        # play is idempotent on the live motion.
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list, stretch=1)

        controls = self._build_controls()
        layout.addWidget(controls)

        self._scrub = QSlider(Qt.Orientation.Horizontal)
        self._scrub.setRange(0, _SCRUB_STEPS)
        self._scrub.sliderMoved.connect(self._on_scrub_moved)
        layout.addWidget(self._scrub)

        self._time_label = QLabel("0.00 / 0.00 s")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._time_label)

        self.setWidget(self._inner)

        canvas.document_loaded.connect(self._rebuild_motions)
        self._player.state_changed.connect(self._refresh_transport)
        self._rebuild_motions()
        self._refresh_transport()

    # ---- public -------------------------------------------------------

    def player(self) -> MotionPlayer:
        return self._player

    def select_motion(self, name: str) -> bool:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.text() == name:
                self._list.setCurrentRow(i)
                self._activate_motion(name)
                return True
        return False

    # ---- rebuild ------------------------------------------------------

    def _rebuild_motions(self) -> None:
        self._list.clear()
        document = self._canvas.document()
        if document is None or not document.motions:
            placeholder = QListWidgetItem(
                language_wrapper.language_word_dict.get(
                    "puppet_motions_empty", "(No motions)",
                ),
            )
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._list.addItem(placeholder)
            self._player.set_motion(None)
            return
        for motion in document.motions:
            self._list.addItem(QListWidgetItem(motion.name))

    def _build_controls(self) -> QWidget:
        lang = language_wrapper.language_word_dict
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._play_btn = QPushButton(lang.get("puppet_play", "Play"))
        self._play_btn.clicked.connect(self._on_play)
        row.addWidget(self._play_btn)

        self._pause_btn = QPushButton(lang.get("puppet_pause", "Pause"))
        self._pause_btn.clicked.connect(self._player.pause)
        row.addWidget(self._pause_btn)

        self._stop_btn = QPushButton(lang.get("puppet_stop", "Stop"))
        self._stop_btn.clicked.connect(self._player.stop)
        row.addWidget(self._stop_btn)

        self._loop_box = QCheckBox(lang.get("puppet_loop", "Loop"))
        self._loop_box.setChecked(self._player.loop())
        self._loop_box.toggled.connect(self._player.set_loop)
        row.addWidget(self._loop_box)

        return wrapper

    # ---- slots --------------------------------------------------------

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Single-click handler — bind the picked motion and start
        playing so users see the motion immediately. The dock's Stop
        button is the way to silence playback."""
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        self._activate_motion(item.text())
        self._player.play()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Double-click runs the same path as single-click. Kept for
        users with muscle memory from the old behaviour."""
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        self._activate_motion(item.text())
        self._player.play()

    def _activate_motion(self, name: str) -> None:
        document = self._canvas.document()
        if document is None:
            return
        match = next((m for m in document.motions if m.name == name), None)
        if match is None:
            return
        self._player.set_motion(match)
        self.motion_picked.emit(name)

    def _on_play(self) -> None:
        if self._player.motion() is None and self._list.currentItem() is not None:
            item = self._list.currentItem()
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                self._activate_motion(item.text())
        self._player.play()

    def _on_scrub_moved(self, step: int) -> None:
        duration = self._player.duration()
        if duration <= 0:
            return
        self._player.seek(duration * step / _SCRUB_STEPS)

    def _refresh_transport(self) -> None:
        playing = self._player.is_playing()
        self._play_btn.setEnabled(not playing)
        self._pause_btn.setEnabled(playing)
        elapsed = self._player.elapsed()
        duration = self._player.duration()
        self._time_label.setText(f"{elapsed:.2f} / {duration:.2f} s")
        if duration > 0:
            self._scrub.blockSignals(True)
            self._scrub.setValue(int(elapsed / duration * _SCRUB_STEPS))
            self._scrub.blockSignals(False)
