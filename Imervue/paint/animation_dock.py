"""Animation timeline dock — frame strip + transport controls.

Wraps :class:`Imervue.paint.animation_timeline.AnimationTimeline` in
a horizontal strip of thumbnail buttons + transport (Add / Remove /
Play / Stop) + an FPS spinner. The dock owns the playback QTimer
that advances the playhead while playing.

Signals
-------

* :attr:`frame_selected` — emitted when the user clicks a thumbnail
  or playback advances. The workspace listens and pushes the frame
  back onto the active canvas.
* :attr:`add_frame_requested` — fired on the Add button; the
  workspace responds by snapshotting the current canvas and adding
  it to the timeline.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.animation_timeline import (
    FPS_MAX,
    FPS_MIN,
    AnimationTimeline,
    thumbnail_for,
)

THUMBNAIL_PX = 64


class AnimationDock(QDockWidget):
    """Frame strip with transport controls."""

    frame_selected = Signal(int)         # index of newly active frame
    add_frame_requested = Signal()
    remove_frame_requested = Signal(int)

    def __init__(self, timeline: AnimationTimeline | None = None, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(
            lang.get("paint_dock_animation", "Animation"), parent,
        )
        self._timeline = timeline if timeline is not None else AnimationTimeline()
        self._is_playing = False

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)

        # Top row — transport buttons.
        controls = QHBoxLayout()
        self._add_btn = QPushButton(lang.get(
            "paint_animation_add_frame", "+ Frame",
        ))
        self._add_btn.clicked.connect(lambda: self.add_frame_requested.emit())
        self._add_btn.setToolTip(lang.get(
            "paint_animation_add_frame_tooltip",
            "Snapshot the current canvas as a new animation frame",
        ))
        controls.addWidget(self._add_btn)

        self._remove_btn = QPushButton(lang.get(
            "paint_animation_remove_frame", "− Frame",
        ))
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        self._remove_btn.setToolTip(lang.get(
            "paint_animation_remove_frame_tooltip",
            "Remove the selected frame from the timeline",
        ))
        controls.addWidget(self._remove_btn)

        self._play_btn = QPushButton(lang.get(
            "paint_animation_play", "▶ Play",
        ))
        self._play_btn.clicked.connect(self.toggle_playback)
        self._play_btn.setToolTip(lang.get(
            "paint_animation_play_tooltip",
            "Cycle the timeline at the chosen FPS",
        ))
        controls.addWidget(self._play_btn)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(FPS_MIN, FPS_MAX)
        self._fps_spin.setValue(self._timeline.fps)
        self._fps_spin.setToolTip(lang.get(
            "paint_animation_fps_tooltip",
            "Playback frames per second",
        ))
        self._fps_spin.setSuffix(" fps")
        self._fps_spin.valueChanged.connect(self._on_fps_changed)
        controls.addWidget(self._fps_spin)
        controls.addStretch(1)
        layout.addLayout(controls)

        # Frame strip — horizontal scroll of thumbnail buttons.
        self._strip_scroll = QScrollArea()
        self._strip_scroll.setWidgetResizable(True)
        self._strip_host = QWidget()
        self._strip_layout = QHBoxLayout(self._strip_host)
        self._strip_layout.setContentsMargins(0, 0, 0, 0)
        self._strip_layout.setSpacing(2)
        self._strip_layout.addStretch(1)
        self._strip_scroll.setWidget(self._strip_host)
        self._strip_scroll.setMinimumHeight(THUMBNAIL_PX + 24)
        layout.addWidget(self._strip_scroll)

        self.setWidget(body)

        # Playback timer — interval is set from the FPS spinner.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._refresh_strip()

    # ---- public API -----------------------------------------------------

    def timeline(self) -> AnimationTimeline:
        return self._timeline

    def set_timeline(self, timeline: AnimationTimeline) -> None:
        """Replace the bound timeline and refresh."""
        self._timeline = timeline
        self._fps_spin.setValue(self._timeline.fps)
        self._refresh_strip()

    def is_playing(self) -> bool:
        return self._is_playing

    def toggle_playback(self) -> None:
        if self._is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self) -> None:
        if self._is_playing or len(self._timeline) <= 1:
            return
        self._is_playing = True
        interval_ms = max(1, int(round(1000.0 / self._timeline.fps)))
        self._timer.start(interval_ms)
        self._play_btn.setText(language_wrapper.language_word_dict.get(
            "paint_animation_stop", "■ Stop",
        ))

    def stop_playback(self) -> None:
        if not self._is_playing:
            return
        self._timer.stop()
        self._is_playing = False
        self._play_btn.setText(language_wrapper.language_word_dict.get(
            "paint_animation_play", "▶ Play",
        ))

    def refresh(self) -> None:
        """Re-build the thumbnail strip — call after frames change."""
        self._refresh_strip()

    # ---- slot handlers --------------------------------------------------

    def _on_remove_clicked(self) -> None:
        idx = self._timeline.current_index
        if 0 <= idx < len(self._timeline.frames) and len(self._timeline.frames) > 1:
            self.remove_frame_requested.emit(idx)

    def keyPressEvent(self, event) -> None:  # pragma: no cover - Qt UI
        """Delete / Backspace removes the currently-selected frame.

        Mirrors the file-tree / layer-dock conventions so a user who
        clicks a frame thumbnail and presses Delete sees it disappear
        without first hunting for the ``− Frame`` button. Last-frame
        protection still lives in
        :meth:`AnimationTimeline.remove_frame` — pressing Delete on a
        timeline with one frame is a no-op rather than an error.
        """
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._on_remove_clicked()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_fps_changed(self, fps: int) -> None:
        self._timeline.set_fps(int(fps))
        if self._is_playing:
            interval_ms = max(1, int(round(1000.0 / self._timeline.fps)))
            self._timer.setInterval(interval_ms)

    def _on_tick(self) -> None:
        if not self._timeline.frames:
            self.stop_playback()
            return
        new_idx = self._timeline.advance(loop=True)
        self.frame_selected.emit(new_idx)
        self._highlight_active()

    # ---- thumbnail strip rebuild ---------------------------------------

    def _refresh_strip(self) -> None:
        # Clear all current children except the trailing stretch.
        while self._strip_layout.count() > 1:
            child = self._strip_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        for i, frame in enumerate(self._timeline.frames):
            btn = self._make_thumbnail(i, frame.image)
            self._strip_layout.insertWidget(self._strip_layout.count() - 1, btn)
        self._highlight_active()
        # Last-frame protection: ``AnimationTimeline.remove_frame``
        # refuses to drop the only remaining frame so the dock always
        # has something to show. Reflect that in the toolbar button so
        # the user doesn't think the action is broken when nothing
        # happens.
        self._remove_btn.setEnabled(len(self._timeline.frames) > 1)

    def _make_thumbnail(self, index: int, image: np.ndarray) -> QToolButton:
        btn = QToolButton()
        btn.setCheckable(True)
        btn.setIconSize(QPixmap(THUMBNAIL_PX, THUMBNAIL_PX).size())
        from Imervue.paint.animation_timeline import Frame
        thumb = thumbnail_for(Frame(image=image), size=THUMBNAIL_PX)
        thumb_contig = np.ascontiguousarray(thumb)
        h, w = thumb_contig.shape[:2]
        qimg = QImage(
            thumb_contig.data, w, h, w * 4, QImage.Format.Format_RGBA8888,
        )
        pix = QPixmap.fromImage(qimg.copy())
        btn.setIcon(pix)
        btn.setText(str(index + 1))
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.clicked.connect(lambda *_, i=index: self._on_frame_clicked(i))
        # Right-click → context menu with a Delete entry. Mirrors the
        # right-click-to-delete pattern used by the layer dock so the
        # user has three independent ways to drop a frame: button,
        # Delete key, or context menu.
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda pos, b=btn, i=index: self._show_thumbnail_menu(b, pos, i),
        )
        return btn

    def _show_thumbnail_menu(  # pragma: no cover - Qt UI
        self, button: QToolButton, pos: QPoint, index: int,
    ) -> None:
        lang = language_wrapper.language_word_dict
        menu = QMenu(button)
        delete_action = menu.addAction(
            lang.get("paint_animation_delete_frame", "Delete frame"),
        )
        # Last-frame protection — the timeline refuses to drop the
        # only remaining frame, so disable the entry rather than
        # firing a no-op signal.
        delete_action.setEnabled(len(self._timeline.frames) > 1)
        chosen = menu.exec(button.mapToGlobal(pos))
        if chosen is delete_action:
            self.remove_frame_requested.emit(index)

    def _on_frame_clicked(self, index: int) -> None:
        if self._timeline.set_current_index(index):
            self.frame_selected.emit(index)
        self._highlight_active()

    def _highlight_active(self) -> None:
        active = self._timeline.current_index
        for i in range(self._strip_layout.count() - 1):
            child = self._strip_layout.itemAt(i)
            widget = child.widget() if child is not None else None
            if isinstance(widget, QToolButton):
                widget.setChecked(i == active)
