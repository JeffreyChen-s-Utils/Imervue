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
