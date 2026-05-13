"""Batch-export every motion in a :class:`PuppetDocument` to a video
file (MP4 / GIF / WebM).

Drives the existing :class:`RecordingSession` over each motion
sequentially: rebind, play from ``t=0``, record for ``motion.duration``
seconds, save as ``{motion.name}.{ext}``, advance. The orchestration
is a QObject state machine so the caller can wire progress / finished
signals into a status bar without writing the loop manually.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal

from Imervue.puppet.recorder import RecordingSession

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.document import Motion
    from Imervue.puppet.motion_player import MotionPlayer

logger = logging.getLogger("Imervue.plugin.puppet.batch_export")

DEFAULT_FPS: int = 30
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".mp4", ".gif", ".webm")


class BatchMotionExporter(QObject):
    """Sequentially exports every motion in a document.

    Hand it a canvas + player + output directory + extension, call
    :meth:`start`, and listen for :attr:`progress` ticks plus
    :attr:`finished` (or :attr:`failed`) once the queue empties."""

    progress = Signal(int, int, str)
    """Emitted before each motion: ``(index, total, motion_name)``."""

    finished = Signal(list)
    """Emitted with the list of written file paths once the queue
    drains successfully."""

    failed = Signal(str)
    """Emitted with the failure reason; partial output stays on disk."""

    def __init__(
        self,
        canvas: PuppetCanvas,
        player: MotionPlayer,
        parent=None,
    ):
        super().__init__(parent)
        self._canvas = canvas
        self._player = player
        self._recorder = RecordingSession(canvas, self)
        self._directory: Path | None = None
        self._extension: str = ".mp4"
        self._fps: int = DEFAULT_FPS
        self._queue: list[Motion] = []
        self._index: int = 0
        self._total: int = 0
        self._written: list[str] = []
        self._active: bool = False
        self._recorder.finished.connect(self._on_recorder_finished)
        self._recorder.failed.connect(self._on_recorder_failed)

    def is_running(self) -> bool:
        return self._active

    def start(
        self,
        directory: str | Path,
        *,
        extension: str = ".mp4",
        fps: int = DEFAULT_FPS,
    ) -> bool:
        """Begin the batch. Returns ``False`` and emits :attr:`failed`
        if the document has no motions, the extension isn't supported,
        or the output directory doesn't exist."""
        if self._active:
            return False
        if extension.lower() not in SUPPORTED_EXTENSIONS:
            self.failed.emit(
                f"unsupported extension {extension!r}; "
                f"expected one of {SUPPORTED_EXTENSIONS}",
            )
            return False
        out = Path(directory)
        if not out.is_dir():
            self.failed.emit(f"output directory {out} does not exist")
            return False
        document = self._canvas.document()
        if document is None or not document.motions:
            self.failed.emit("document has no motions to export")
            return False
        self._directory = out
        self._extension = extension.lower()
        self._fps = max(1, int(fps))
        self._queue = list(document.motions)
        self._index = 0
        self._total = len(self._queue)
        self._written = []
        self._active = True
        self._record_next()
        return True

    def stop(self) -> None:
        """Cancel the batch. Whatever's been written so far stays on
        disk; the current in-flight recording is closed cleanly."""
        if not self._active:
            return
        self._active = False
        if self._recorder.is_recording():
            self._recorder.stop()

    # ---- state machine ----------------------------------------------

    def _record_next(self) -> None:
        if not self._active or self._index >= len(self._queue):
            self._finish_clean()
            return
        motion = self._queue[self._index]
        self.progress.emit(self._index, self._total, motion.name)
        path = self._destination_for(motion)
        # Drive the player to render this motion from frame 0.
        self._player.set_motion(motion)
        self._player.seek(0.0)
        self._player.play()
        if not self._recorder.start(path, fps=self._fps):
            # ``failed`` already emitted by RecordingSession; defensive
            # state cleanup so subsequent calls to ``start`` work.
            self._active = False
            return
        # Stop the recorder when the motion completes; +250 ms cushion
        # so the closing frame lands inside the clip.
        QTimer.singleShot(
            int(motion.duration * 1000) + 250,
            self._stop_current_recording,
        )

    def _stop_current_recording(self) -> None:
        if self._recorder.is_recording():
            self._recorder.stop()

    def _on_recorder_finished(self, path: str) -> None:
        if not self._active:
            return
        self._written.append(path)
        self._player.pause()
        self._index += 1
        self._record_next()

    def _on_recorder_failed(self, reason: str) -> None:
        self._active = False
        self.failed.emit(reason)

    def _finish_clean(self) -> None:
        self._active = False
        self.finished.emit(list(self._written))

    def _destination_for(self, motion: Motion) -> str:
        if self._directory is None:
            raise RuntimeError("destination unset — start() not called")
        safe = _safe_filename(motion.name)
        return str(self._directory / f"{safe}{self._extension}")


def _safe_filename(name: str) -> str:
    """Strip filesystem-unfriendly characters from a motion name so
    the export path is always writable. Falls back to ``motion`` when
    every character was stripped."""
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")
    return cleaned or "motion"
