"""
圖片整理執行緒
Image Organizer worker — copy or move each planned group into its subfolder of
the output folder off the GUI thread, renaming on a name collision and carrying
the sidecars along.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from Imervue.system.file_transfer import carry_sidecars

logger = logging.getLogger("Imervue.image_organizer")


class _OrganizerWorker(QThread):
    progress = Signal(int, int, str)   # current, total, filename
    result_ready = Signal(int, int)    # success, failed
    # {old: new} of the files moved, for their saved data to follow on the GUI thread
    files_moved = Signal(dict)

    def __init__(
        self,
        plan: dict[str, list[str]],
        output_dir: str,
        move: bool,
        parent=None,
    ):
        super().__init__(parent)
        self._plan = plan
        self._output_dir = output_dir
        self._move = move
        self._abort = False
        self._moved: dict[str, str] = {}

    def abort(self):
        self._abort = True

    def run(self):
        total = sum(len(v) for v in self._plan.values())
        state = {"done": 0, "success": 0, "failed": 0}
        for subfolder, paths in self._plan.items():
            dest_dir = os.path.join(self._output_dir, subfolder)
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except OSError:
                # An unwritable output folder fails the group; escaping, the error
                # left the dialog waiting for a result that never came.
                logger.exception("Could not create %s", dest_dir)
                state["done"] += len(paths)
                state["failed"] += len(paths)
                continue
            if self._process_group(paths, dest_dir, total, state):
                break
        if self._moved:
            self.files_moved.emit(dict(self._moved))
        self.result_ready.emit(state["success"], state["failed"])

    def _process_group(self, paths, dest_dir: str, total: int, state: dict) -> bool:
        """Return True if we aborted mid-way."""
        for src in paths:
            if self._abort:
                return True
            state["done"] += 1
            name = os.path.basename(src)
            self.progress.emit(state["done"], total, name)
            dest = self._resolve_collision(os.path.join(dest_dir, name))
            if self._transfer(src, dest):
                state["success"] += 1
            else:
                state["failed"] += 1
        return False

    @staticmethod
    def _resolve_collision(dest: str) -> str:
        if not os.path.exists(dest):
            return dest
        dir_name = os.path.dirname(dest)
        name = os.path.basename(dest)
        stem = Path(name).stem
        ext = Path(name).suffix
        counter = 1
        candidate = dest
        while os.path.exists(candidate):
            candidate = os.path.join(dir_name, f"{stem}_{counter}{ext}")
            counter += 1
        return candidate

    def _transfer(self, src: str, dest: str) -> bool:
        try:
            if self._move:
                shutil.move(src, dest)
            else:
                shutil.copy2(src, dest)
        except OSError:
            # shutil.Error inherits from OSError, so the bare OSError catches both.
            logger.exception("Failed to %s %s", "move" if self._move else "copy", src)
            return False
        # The XMP / annotation sidecars go along; the saved rating, tags and
        # library rows are re-keyed on the GUI thread (files_moved).
        carry_sidecars([(src, dest)], move=self._move)
        if self._move:
            self._moved[src] = dest
        return True
