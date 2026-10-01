"""Characterisation tests for ``GifVideoDialog``'s layout and control wiring.

Pins the frame list (order, path data, drag mode), the move buttons, the
settings group (format, FPS, size spins with their "Auto" value, loop box and
its GIF-only visibility), the output row, and the Cancel / Create row, so
restructuring ``_build_ui`` cannot drop, reorder or rewire a control.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QLabel, QListWidget, QProgressBar, QPushButton, QSpinBox,
)

from Imervue.gui import gif_video_dialog as mod
from Imervue.gui.gif_video_dialog import GifVideoDialog

_PATHS = ["C:/shots/one.png", "C:/shots/two.png", "C:/shots/three.png"]


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(mod.language_wrapper, "language_word_dict", {})


@pytest.fixture
def dialog(qapp):
    dlg = GifVideoDialog(SimpleNamespace(main_window=None), list(_PATHS))
    yield dlg
    dlg.deleteLater()


def _items(dlg):
    layout = dlg.layout()
    return [layout.itemAt(i).widget() or layout.itemAt(i).layout() for i in range(layout.count())]


def _row(layout):
    return [layout.itemAt(i).widget() for i in range(layout.count())]


def test_top_level_order(dialog):
    kinds = [type(x).__name__ for x in _items(dialog)]
    assert kinds == ["QLabel", "QListWidget", "QHBoxLayout", "QGroupBox", "QHBoxLayout",
                     "QProgressBar", "QLabel", "QHBoxLayout"]
    assert _items(dialog)[0].text() == "Drag to reorder (top = first frame):"


def test_frame_list(dialog):
    lst = _items(dialog)[1]
    assert lst is dialog._list and isinstance(lst, QListWidget)  # noqa: SLF001
    assert lst.dragDropMode() == QListWidget.DragDropMode.InternalMove
    assert [lst.item(i).text() for i in range(lst.count())] == ["one.png", "two.png", "three.png"]
    assert [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())] == _PATHS


def test_order_row_moves_items(dialog):
    up, down, stretch = _row(_items(dialog)[2])
    assert (up.text(), down.text(), stretch) == ("Move Up", "Move Down", None)
    lst = dialog._list  # noqa: SLF001
    lst.setCurrentRow(1)
    up.click()
    assert lst.item(0).text() == "two.png"
    down.click()
    assert lst.item(1).text() == "two.png"


def test_settings_group(dialog):
    group = _items(dialog)[3]
    assert isinstance(group, QGroupBox) and group.title() == "Settings"
    lay = group.layout()
    fmt_row, fps_row, size_row = (lay.itemAt(i).layout() for i in range(3))
    loop = lay.itemAt(3).widget()
    label, combo = _row(fmt_row)
    assert label.text() == "Format:" and combo is dialog._fmt_combo  # noqa: SLF001
    assert isinstance(combo, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())] == ["GIF", "MP4"]
    fps_label, fps, fps_stretch = _row(fps_row)
    assert fps_label.text() == "FPS:" and fps is dialog._fps_spin and fps_stretch is None  # noqa: SLF001
    assert (fps.minimum(), fps.maximum(), fps.value()) == (1, 60, 5)
    w_label, width, h_label, height = _row(size_row)
    assert (w_label.text(), h_label.text()) == ("Width:", "Height:")
    for spin, attr in ((width, "_width_spin"), (height, "_height_spin")):
        assert isinstance(spin, QSpinBox) and spin is getattr(dialog, attr)
        assert (spin.minimum(), spin.maximum(), spin.value()) == (0, 99999, 0)
        assert spin.specialValueText() == "Auto"
    assert isinstance(loop, QCheckBox) and loop is dialog._loop_check  # noqa: SLF001
    assert loop.text() == "Loop forever" and loop.isChecked()


def test_loop_box_only_for_gif(dialog):
    combo, loop = dialog._fmt_combo, dialog._loop_check  # noqa: SLF001
    combo.setCurrentText("MP4")
    assert loop.isHidden()
    combo.setCurrentText("GIF")
    assert not loop.isHidden()


def test_progress_status_and_buttons(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(GifVideoDialog, "_on_cancel", lambda self, *_a: calls.append("cancel"))
    monkeypatch.setattr(GifVideoDialog, "_do_create", lambda self, *_a: calls.append("create"))
    dlg = GifVideoDialog(SimpleNamespace(main_window=None), list(_PATHS))
    try:
        items = _items(dlg)
        assert isinstance(items[5], QProgressBar) and items[5].isHidden()
        assert isinstance(items[6], QLabel) and items[6] is dlg._status_label  # noqa: SLF001
        stretch, cancel, create = _row(items[7])
        assert stretch is None and cancel.text() == "Cancel"
        assert create is dlg._create_btn and create.text() == "Create"  # noqa: SLF001
        assert isinstance(create, QPushButton)
        cancel.click()
        create.click()
        assert calls == ["cancel", "create"]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Output path: a free suggestion, and no replacing unasked
# ---------------------------------------------------------------------------


@pytest.fixture
def frames_in(qapp, tmp_path):
    """A dialog over two frames in *tmp_path* (made after any files the test creates)."""
    made = []

    def make():
        dlg = GifVideoDialog(SimpleNamespace(main_window=None),
                             [str(tmp_path / "a.png"), str(tmp_path / "b.png")])
        made.append(dlg)
        return dlg

    yield make
    for dlg in made:
        dlg.deleteLater()


@pytest.fixture
def replace_answers(monkeypatch):
    """Record every "replace it?" question and answer it with ``answers["reply"]``."""
    from PySide6.QtWidgets import QMessageBox
    answers = {"reply": False, "asked": []}

    def question(_parent, _title, text, *_rest):
        answers["asked"].append(text)
        return QMessageBox.StandardButton.Yes if answers["reply"] else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", question)
    return answers


def test_the_suggested_output_keeps_an_earlier_result(frames_in, tmp_path):
    """Every GIF made from one folder was suggested as output.gif and replaced the last."""
    (tmp_path / "output.gif").write_bytes(b"made last week")
    dlg = frames_in()
    assert Path(dlg._path_edit.text()) == tmp_path / "output_1.gif"  # noqa: SLF001


def test_switching_format_renames_the_suggestion_freely(frames_in, tmp_path):
    (tmp_path / "output.gif").write_bytes(b"x")
    dlg = frames_in()
    dlg._fmt_combo.setCurrentText("MP4")  # noqa: SLF001
    assert Path(dlg._path_edit.text()) == tmp_path / "output.mp4"  # noqa: SLF001
    dlg._fmt_combo.setCurrentText("GIF")  # noqa: SLF001
    assert Path(dlg._path_edit.text()) == tmp_path / "output_1.gif"  # noqa: SLF001


def test_switching_format_keeps_a_typed_name(frames_in, tmp_path):
    dlg = frames_in()
    dlg._path_edit.setText(str(tmp_path / "trip.gif"))  # noqa: SLF001
    dlg._fmt_combo.setCurrentText("MP4")  # noqa: SLF001
    assert Path(dlg._path_edit.text()) == tmp_path / "trip.mp4"  # noqa: SLF001


def test_creating_over_a_typed_existing_file_asks_first(
        frames_in, replace_answers, tmp_path, monkeypatch):
    monkeypatch.setattr(mod._CreateWorker, "start", lambda self: None)  # noqa: SLF001
    taken = tmp_path / "trip.gif"
    taken.write_bytes(b"made last week")
    dlg = frames_in()
    dlg._path_edit.setText(str(taken))  # noqa: SLF001
    dlg._do_create()  # noqa: SLF001
    assert dlg._worker is None  # noqa: SLF001
    assert len(replace_answers["asked"]) == 1 and "trip.gif" in replace_answers["asked"][0]
    replace_answers["reply"] = True
    dlg._do_create()  # noqa: SLF001
    assert dlg._worker is not None  # noqa: SLF001
    dlg._worker = None  # noqa: SLF001


def test_a_file_picked_through_browse_is_not_asked_twice(
        frames_in, replace_answers, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(mod._CreateWorker, "start", lambda self: None)  # noqa: SLF001
    taken = tmp_path / "trip.gif"
    taken.write_bytes(b"made last week")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(taken), ""))
    dlg = frames_in()
    dlg._browse()  # noqa: SLF001
    dlg._do_create()  # noqa: SLF001
    assert replace_answers["asked"] == []
    assert dlg._worker is not None  # noqa: SLF001
    dlg._worker = None  # noqa: SLF001


# ---------------------------------------------------------------------------
# GIF looping
# ---------------------------------------------------------------------------


def _made_gif(tmp_path, loop):
    from PIL import Image
    frames = []
    for i, colour in enumerate(("red", "blue")):
        frame = tmp_path / f"f{i}.png"
        Image.new("RGB", (8, 8), colour).save(frame)
        frames.append(str(frame))
    out = tmp_path / "out.gif"
    results = []
    worker = mod._CreateWorker(frames, str(out), "GIF", 10, 0, 0, loop)  # noqa: SLF001
    worker.result_ready.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    worker.deleteLater()
    assert results == [(True, str(out))]
    return out.read_bytes()


def test_a_looping_gif_loops_forever(qapp, tmp_path):
    data = _made_gif(tmp_path, loop=True)
    netscape = data.find(b"NETSCAPE2.0")
    assert netscape >= 0
    # Block size 3, sub-block id 1, then the little-endian loop count: 0 = forever.
    assert data[netscape + 11:netscape + 15] == b"\x03\x01\x00\x00"


def test_a_gif_without_loop_plays_once(qapp, tmp_path):
    """Loop count 1 was written, which browsers play twice (one repeat)."""
    assert b"NETSCAPE2.0" not in _made_gif(tmp_path, loop=False)



def test_ffmpeg_is_found_through_imageio_ffmpeg(monkeypatch):
    """MP4 needed ffmpeg on PATH, though the documented optional dependency is imageio-ffmpeg."""
    import shutil
    import sys
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg",
                        SimpleNamespace(get_ffmpeg_exe=lambda: "C:/bundled/ffmpeg.exe"))
    assert mod.find_ffmpeg() == "C:/bundled/ffmpeg.exe"


def test_ffmpeg_on_path_comes_first(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _name: "C:/tools/ffmpeg.exe")
    assert mod.find_ffmpeg() == "C:/tools/ffmpeg.exe"


def test_no_ffmpeg_anywhere(monkeypatch):
    import shutil
    import sys

    def no_binary():
        raise RuntimeError("no ffmpeg exe could be found")

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", SimpleNamespace(get_ffmpeg_exe=no_binary))
    assert mod.find_ffmpeg() is None
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    assert mod.find_ffmpeg() is None


def test_an_mp4_is_made_from_odd_sized_frames(qapp, tmp_path):
    """libx264 refused a 63 x 47 frame ("width not divisible by 2") and the video failed."""
    from PIL import Image
    if mod.find_ffmpeg() is None:
        pytest.skip("no ffmpeg on this machine")
    frames = []
    for i, colour in enumerate(("red", "blue", "green")):
        frame = tmp_path / f"f{i}.png"
        Image.new("RGB", (63, 47), colour).save(frame)
        frames.append(str(frame))
    out = tmp_path / "out.mp4"
    results = []
    worker = mod._CreateWorker(frames, str(out), "MP4", 10, 0, 0, False)  # noqa: SLF001
    worker.result_ready.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    worker.deleteLater()
    assert results == [(True, str(out))]
    assert out.stat().st_size > 0
