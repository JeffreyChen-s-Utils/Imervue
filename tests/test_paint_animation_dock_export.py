"""The Animation dock exports its frames as an animated GIF, WebP or PNG.

``paint/animation_export.py`` could write all three but only from the
document-based ``Animation``, which nothing in the UI builds, and no dock
offered it; the docs said there was no animation export. It now also takes the
dock's ``AnimationTimeline`` (each frame shown for ``1000 / fps`` ms), and the
dock's **Export…** button writes the format the chosen file name names.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.animation_dock import AnimationDock
from Imervue.paint.animation_export import export_animation
from Imervue.paint.animation_timeline import AnimationTimeline
from tests._toast_spy import ToastSpy


def _timeline(fps: int = 10, count: int = 3) -> AnimationTimeline:
    timeline = AnimationTimeline(fps=fps)
    for i in range(count):
        frame = np.zeros((6, 8, 4), np.uint8)
        frame[..., i % 3] = 255
        frame[..., 3] = 255
        timeline.add_frame(frame)
    return timeline


def _frames(path) -> list[np.ndarray]:
    with Image.open(path) as img:
        out = []
        for i in range(getattr(img, "n_frames", 1)):
            img.seek(i)
            out.append(np.array(img.convert("RGBA")))
        return out


@pytest.mark.parametrize("name", ["clip.gif", "clip.webp", "clip.png", "clip.apng", "CLIP.GIF"])
def test_the_suffix_picks_the_format_and_every_frame_is_written(tmp_path, name):
    export_animation(_timeline(), tmp_path / name)
    frames = _frames(tmp_path / name)
    assert len(frames) == 3
    assert [tuple(f[0, 0, :3]) for f in frames] == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]


def test_each_frame_lasts_one_fps_tick(tmp_path):
    export_animation(_timeline(fps=8), tmp_path / "clip.png")    # APNG keeps whole milliseconds
    with Image.open(tmp_path / "clip.png") as img:
        assert img.info["duration"] == 125


def test_webp_is_written_without_loss(tmp_path):
    timeline = _timeline(count=1)
    timeline.frames[0].image[2, 3] = (17, 99, 201, 255)
    export_animation(timeline, tmp_path / "clip.webp")
    np.testing.assert_array_equal(_frames(tmp_path / "clip.webp")[0], timeline.frames[0].image)


def test_gif_keeps_transparent_pixels_transparent(tmp_path):
    timeline = _timeline(count=1)
    timeline.frames[0].image[:3, :] = 0
    export_animation(timeline, tmp_path / "clip.gif")
    alpha = _frames(tmp_path / "clip.gif")[0][..., 3]
    assert (alpha[:3] == 0).all() and (alpha[3:] == 255).all()


def test_an_unknown_suffix_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no animation format"):
        export_animation(_timeline(), tmp_path / "clip.mp4")


def test_an_empty_timeline_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no frames"):
        export_animation(AnimationTimeline(), tmp_path / "clip.gif")


# --- the dock ---------------------------------------------------------------

class _Host:
    """The dock's parent workspace, reduced to its toast."""

    def __init__(self):
        self.toast = ToastSpy()


@pytest.fixture
def dock(qapp, monkeypatch):
    widget = AnimationDock(_timeline())
    host = _Host()
    monkeypatch.setattr(widget, "parent", lambda: host)
    yield widget, host.toast
    widget.deleteLater()


def test_export_is_offered_only_with_frames(qapp):
    empty = AnimationDock(AnimationTimeline())
    full = AnimationDock(_timeline())
    try:
        assert not empty._export_btn.isEnabled()
        assert full._export_btn.isEnabled()
    finally:
        empty.deleteLater()
        full.deleteLater()


def test_export_to_writes_the_file_and_says_so(dock, tmp_path):
    widget, toast = dock
    assert widget.export_to(str(tmp_path / "walk.webp")) is True
    assert len(_frames(tmp_path / "walk.webp")) == 3
    assert toast.calls == [("success", "Exported animation: walk.webp")]


def test_a_name_without_a_suffix_becomes_a_gif(dock, tmp_path):
    widget, _toast = dock
    assert widget.export_to(str(tmp_path / "walk")) is True
    assert (tmp_path / "walk.gif").is_file()


def test_a_failed_export_reports_and_returns_false(dock, tmp_path):
    widget, toast = dock
    assert widget.export_to(str(tmp_path / "walk.mp4")) is False
    (kind, text), = toast.calls
    assert kind == "error" and text.startswith("Animation export failed: ")


def test_without_a_toast_an_error_goes_to_a_message_box(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(args[2]))
    widget = AnimationDock(_timeline())
    monkeypatch.setattr(widget, "parent", lambda: SimpleNamespace())
    try:
        assert widget.export_to(str(tmp_path / "walk.mp4")) is False
        assert shown and shown[0].startswith("Animation export failed: ")
    finally:
        widget.deleteLater()
