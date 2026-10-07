"""Fresh-process autosave/crash/recovery probe; only the supplied scratch profile is touched."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import monotonic, sleep

import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.performance_support import isolated_profile  # noqa: E402


def run(mode: str, directory: Path) -> None:
    from Imervue.paint import auto_save
    from Imervue.paint.document import PaintDocument
    from Imervue.paint.undo_stack import UndoStack
    from Imervue.paint.workspace_autosave import AutosaveMixin

    app = QApplication([])

    class Canvas:
        def __init__(self, value=17):
            self._doc = PaintDocument()
            self._doc.load_image(np.full((4, 5, 4), value, dtype=np.uint8))

        def document(self):
            return self._doc

        def set_document(self, document):
            self._doc = document

    class Host(QObject, AutosaveMixin):
        def __init__(self):
            super().__init__()
            self._autosave_target_dir = directory / "snapshots"
            self.canvases, self._tab_dirty, self._undo_stacks = [], {}, {}
            self.new_tab()

        def new_tab(self, **_options):
            self._canvas = Canvas()
            self.canvases.append(self._canvas)
            self._tab_dirty[self._canvas] = True
            self._undo_stacks[self._canvas] = UndoStack(self._canvas.document())
            return self._canvas

        def _set_tab_dirty(self, canvas, dirty):
            self._tab_dirty[canvas] = dirty

        def _refresh_status_line(self):
            pass

    host = Host()
    if mode == "recover":
        restored = host.restore_all_autosaves()
        values = [int(c.document().layer_at(0).image[0, 0, 0]) for c in host.canvases[1:]]
        result = {"restored": restored, "values": sorted(values),
                  "dirty": all(host._tab_dirty[c] for c in host.canvases[1:]),
                  "repeat": host.restore_all_autosaves()}
        (directory / "recovered.json").write_text(json.dumps(result), encoding="utf-8")
        os._exit(0)
    first = host._canvas
    second = host.new_tab()
    second.document().layer_at(0).image.fill(64)
    host._undo_stacks[second].commit()
    host._on_autosave_tick()
    deadline = monotonic() + 30
    while len(getattr(host, "_autosave_written", ())) != 2:
        if monotonic() > deadline:
            raise TimeoutError("two coherent snapshots were not delivered")
        app.processEvents()
        sleep(0.001)
    first.document().layer_at(0).image.fill(31)
    host._undo_stacks[first].commit()

    def crash_before_metadata(*_args):
        os._exit(23)  # bundle is complete, but the new metadata commit never happens

    auto_save.write_text_atomically = crash_before_metadata
    host._on_autosave_tick()
    while monotonic() <= deadline:
        app.processEvents()
        sleep(0.001)
    raise TimeoutError("crash checkpoint was not reached")


if __name__ == "__main__":
    task, folder = sys.argv[1], Path(sys.argv[2])
    with isolated_profile(folder / f"{task}-profile"):
        run(task, folder)
