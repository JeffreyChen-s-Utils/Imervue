"""Tests for the Frame & Caption dialog."""
from __future__ import annotations

import pytest

from Imervue.gui import photo_frame_dialog as mod
from Imervue.gui.photo_frame_dialog import PhotoFrameDialog


@pytest.fixture
def dialog(qapp, tmp_path):
    from PIL import Image
    picture = tmp_path / "shot.png"
    Image.new("RGB", (8, 6), (90, 90, 90)).save(picture)
    dlg = PhotoFrameDialog(None, str(picture))
    yield dlg
    dlg.deleteLater()


def test_the_colours_start_white_and_dark_grey(dialog):
    assert dialog._frame_color.rgb() == (255, 255, 255)  # noqa: SLF001
    assert dialog._text_color.rgb() == (40, 40, 40)  # noqa: SLF001


def test_the_chosen_colours_reach_the_frame(dialog, monkeypatch):
    """The frame was always a white matte: the dialog never passed a colour."""
    sent = []

    class _Worker:
        def __init__(self, path, options, out):
            sent.append(options)
            self.done = type("Sig", (), {"connect": lambda _self, _slot: None})()

        def start(self):
            pass

    monkeypatch.setattr(mod, "_FrameWorker", _Worker)
    dialog._frame_color.set_rgb((0, 0, 0))  # noqa: SLF001
    dialog._text_color.set_rgb((250, 250, 250))  # noqa: SLF001
    dialog._caption.setText("Taipei")  # noqa: SLF001
    dialog._commit()  # noqa: SLF001
    (options,) = sent
    assert options.color == (0, 0, 0)
    assert options.text_color == (250, 250, 250)
    assert options.caption == "Taipei"
    # The stand-in never ran, so there is no thread for the teardown to stop.
    dialog._worker = None  # noqa: SLF001


def test_a_black_frame_is_drawn_black(tmp_path):
    """End to end through the worker: the border pixels are the chosen colour."""
    import numpy as np
    from PIL import Image

    from Imervue.image.photo_frame import FrameOptions
    picture = tmp_path / "shot.png"
    Image.new("RGB", (8, 6), (90, 90, 90)).save(picture)
    out = tmp_path / "framed.png"
    worker = mod._FrameWorker(str(picture), FrameOptions(border=4, color=(0, 0, 0)), str(out))
    got = []
    worker.done.connect(lambda ok, msg: got.append((ok, msg)))
    worker.run()
    assert got == [(True, str(out))]
    with Image.open(out) as framed:
        arr = np.asarray(framed.convert("RGB"))
    assert arr.shape[:2] == (14, 16)
    assert tuple(arr[0, 0]) == (0, 0, 0)
    assert tuple(arr[7, 8]) == (90, 90, 90)
