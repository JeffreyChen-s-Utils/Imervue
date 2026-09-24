"""Tests for the shared apply-and-save helpers (EffectWorker, sliders, paths)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.gui._apply_save import (
    EffectWorker,
    labeled_slider,
    output_path,
)


def test_output_path_tags_sibling_png():
    out = output_path("/photos/raw/IMG_001.jpg", "emboss")
    assert Path(out).name == "IMG_001_emboss.png"
    assert Path(out).parent == Path("/photos/raw")


def test_labeled_slider_initial_and_tracking(qapp):
    slider, label, row = labeled_slider(0, 100, 10, lambda v: f"{v / 100:.2f}")
    assert label.text() == "0.10"
    slider.setValue(50)
    assert label.text() == "0.50"
    assert row is not None


def test_labeled_slider_default_str_format(qapp):
    slider, label, _ = labeled_slider(0, 360, 135)
    assert label.text() == "135"
    slider.setValue(200)
    assert label.text() == "200"


def _sample_png(tmp_path):
    path = tmp_path / "in.png"
    Image.fromarray(
        np.full((6, 6, 4), 120, dtype=np.uint8), mode="RGBA").save(path)
    return path


def test_effect_worker_saves_result(qapp, tmp_path):
    src = _sample_png(tmp_path)
    out = tmp_path / "out.png"
    seen: list[tuple[bool, str]] = []
    worker = EffectWorker(str(src), lambda arr: arr, str(out))
    worker.done.connect(lambda ok, msg: seen.append((ok, msg)))
    worker.run()  # call directly: runs synchronously without spawning a thread
    assert seen == [(True, str(out))]
    assert out.exists()


def test_effect_worker_reports_failure(qapp, tmp_path):
    src = _sample_png(tmp_path)
    out = tmp_path / "out.png"
    seen: list[tuple[bool, str]] = []

    def _boom(_arr):
        raise ValueError("bad effect")

    worker = EffectWorker(str(src), _boom, str(out))
    worker.done.connect(lambda ok, msg: seen.append((ok, msg)))
    worker.run()
    assert len(seen) == 1
    [(ok, message)] = seen  # destructure (no subscript) to satisfy S6466
    assert ok is False
    assert "bad effect" in message
    assert not out.exists()


def test_load_rgba_converts_and_closes_the_file(tmp_path, monkeypatch):
    from Imervue.gui import _apply_save

    path = tmp_path / "rgb.png"
    Image.new("RGB", (3, 2), (10, 20, 30)).save(path)
    opened: list = []
    real_open = Image.open

    def tracking_open(*args, **kwargs):
        img = real_open(*args, **kwargs)
        opened.append(img)
        return img

    monkeypatch.setattr(_apply_save.Image, "open", tracking_open)
    arr = _apply_save.load_rgba(str(path))
    assert arr.shape == (2, 3, 4)
    assert arr.dtype == np.uint8
    assert tuple(arr[0, 0]) == (10, 20, 30, 255)
    assert opened[0].fp is None   # closed, even though still referenced here


def test_load_rgba_keeps_an_rgba_image_as_is(tmp_path):
    from Imervue.gui._apply_save import load_rgba

    path = tmp_path / "rgba.png"
    Image.new("RGBA", (2, 2), (1, 2, 3, 4)).save(path)
    assert tuple(load_rgba(str(path))[1, 1]) == (1, 2, 3, 4)


def test_load_rgba_returns_the_exif_upright_pixels(tmp_path):
    """The tools save without EXIF; a sideways array would be saved sideways for good."""
    from Imervue.gui._apply_save import load_rgba
    arr = np.zeros((20, 40, 3), dtype=np.uint8)
    arr[:, :20] = (255, 0, 0)   # left half of the stored pixels is red
    exif = Image.Exif()
    exif[0x0112] = 6            # rotate 90 CW to view: the red half ends on top
    path = tmp_path / "portrait.png"
    Image.fromarray(arr).save(path, exif=exif)
    out = load_rgba(str(path))
    assert out.shape == (40, 20, 4)
    assert tuple(out[5, 10, :3]) == (255, 0, 0)
    assert tuple(out[35, 10, :3]) == (0, 0, 0)


def test_tools_load_the_current_image_through_load_rgba():
    """An inline ``Image.open(p).convert("RGBA")`` skips the EXIF turn and leaks the handle."""
    import re
    root = Path(__file__).resolve().parent.parent / "Imervue" / "gui"
    inline = re.compile(r'Image\.open\([\w.]+\)\.convert\("RGBA"\)')
    assert sorted(p.name for p in root.glob("*.py") if inline.search(p.read_text(encoding="utf-8"))) == []


def test_load_rgba_develops_raw_and_rasterises_svg(tmp_path, monkeypatch):
    from Imervue.gpu_image_view.images import image_loader
    from Imervue.gui._apply_save import load_rgba
    monkeypatch.setattr(image_loader, "_load_raw",
                        lambda _p, thumbnail: np.zeros((30, 45, 3), dtype=np.uint8))
    assert load_rgba(str(tmp_path / "shot.nef")).shape == (30, 45, 4)
    svg = tmp_path / "a.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="8">'
                   '<rect width="12" height="8" fill="red"/></svg>', encoding="utf-8")
    assert load_rgba(str(svg)).shape == (8, 12, 4)
