"""Inline preview geometry, canonical saves and stale-result protection."""
from __future__ import annotations

import threading
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from Imervue.gui import develop_preview as preview_module
from Imervue.image.recipe import Recipe
from tests import test_develop_panel as shared

main_window = shared.main_window
panel = shared.panel
real_image = shared.real_image
pytestmark = pytest.mark.gui


@pytest.fixture
def large_image(tmp_path):
    path = tmp_path / "large.png"
    Image.new("RGBA", (1600, 1200), (31, 47, 63, 127)).save(path)
    return path


def test_slider_and_refresh_never_apply_recipe_on_ui(panel, real_image, pump_until, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(real_image))
    monkeypatch.setattr(p, "_load_image_with_recipe", lambda *_: pytest.fail("UI recipe apply"))
    p._current = Recipe(exposure=.3)
    p._schedule_preview()
    pump_until(lambda: p._canvas_recipe == p._current)
    np.testing.assert_array_equal(np.array(p._canvas.get_base_pil()),
                                  p._current.apply(np.array(p._decoded_source)))
    p._current = Recipe(exposure=.6)
    p._refresh_canvas_base()
    pump_until(lambda: p._canvas_recipe == p._current)
    assert p._preview_status.text() == ""


def test_reduced_display_keeps_full_geometry_and_coordinates(panel, large_image, pump_until):
    p, _ = panel
    p.bind_to_path(str(large_image))
    p._current = Recipe(rotate_steps=1, crop=(100, 200, 900, 1200), brightness=.2)
    p._request_preview(final=False)
    pump_until(lambda: p._preview.is_idle)
    canvas = p._canvas
    assert canvas._base.size == (900, 1200)
    assert canvas._base_qimg.width() < 900
    assert canvas._base_qimg.height() < 1200
    point = canvas._image_to_screen(450, 600)
    actual = canvas._screen_to_image(point.x(), point.y())
    assert actual == pytest.approx((450, 600))
    assert canvas.isEnabled()
    assert np.all(np.array(canvas._base)[..., 3] == 127)
    assert p._ensure_full_canvas()
    assert canvas._base_qimg.size().width() == 900
    np.testing.assert_array_equal(np.array(canvas.get_base_pil()),
                                  p._current.apply(np.array(p._decoded_source)))


def test_save_from_reduced_preview_uses_full_pixels(panel, large_image, pump_until, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(large_image))
    p._current = Recipe(exposure=.5)
    expected = p._current.apply(np.array(p._decoded_source))
    p._request_preview(final=False)
    pump_until(lambda: p._preview.is_idle)
    assert p._canvas._base_qimg.width() < 1600
    saved = []
    monkeypatch.setattr(p, "_write_over_source", lambda path, image: saved.append(np.array(image)) or True)
    p._save_annotation()
    assert len(saved) == 1
    np.testing.assert_array_equal(saved[0], expected)
    assert saved[0].shape == (1200, 1600, 4)


def test_full_failure_does_not_bake_or_overwrite_old_pixels(panel, real_image, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(real_image))
    p._current = Recipe(exposure=.5)
    monkeypatch.setattr(p, "_load_image_with_recipe", lambda *_: (_ for _ in ()).throw(
        MemoryError("not enough memory")))
    monkeypatch.setattr(p, "_write_over_source", lambda *_: pytest.fail("must not save stale pixels"))
    p._save_annotation()
    assert "not enough memory" in p._preview_status.text()
    assert p._current.exposure == .5


def test_destructive_change_survives_a_stale_full_result(panel, large_image, pump_until, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(large_image))
    started, release = threading.Event(), threading.Event()
    original = preview_module.render_preview

    def render(request, cache, *, full):
        if full:
            started.set()
            if not release.wait(5):
                raise TimeoutError("test must release worker")
            # Simulate a backend that cannot stop and returns obsolete pixels.
            request = replace(request, cancelled=threading.Event())
        return original(request, cache, full=full)

    monkeypatch.setattr(preview_module, "render_preview", render)
    try:
        p._current = Recipe(exposure=.3)
        p._refresh_canvas_base()
        pump_until(started.is_set)
        assert p._ensure_full_canvas()
        changed = Image.new("RGBA", p._canvas._base.size, (77, 88, 99, 127))
        p._canvas._set_base_image(changed)
        release.set()
        pump_until(lambda: p._preview.is_idle)
        assert p._canvas.get_base_pil().getpixel((100, 100)) == (77, 88, 99, 127)
    finally:
        release.set()
        pump_until(lambda: p._preview.is_idle, timeout=5000)


def test_source_switch_drops_old_preview_and_does_not_clear_new_annotations(
    panel, real_image, tmp_path, pump_until,
):
    from Imervue.gui.annotation_models import Annotation
    p, _ = panel
    p.bind_to_path(str(real_image))
    p._current = Recipe(rotate_steps=1)
    p._refresh_canvas_base()
    other = tmp_path / "other.png"
    Image.new("RGBA", (63, 47), (17, 31, 47, 255)).save(other)
    p.bind_to_path(str(other))
    annotation = Annotation(kind="rect", points=[(1, 1), (7, 9)])
    p._canvas.set_annotations([annotation])
    pump_until(lambda: p._preview.is_idle)
    assert p._canvas._base.size == (63, 47)
    assert p._canvas.get_annotations() == [annotation]
    assert p._canvas._base.getpixel((20, 20)) == (17, 31, 47, 255)


def test_benchmark_waits_for_full_result_instead_of_timing_enqueue(panel, real_image, qapp):
    from scripts.performance_benchmark import _measure_modify
    p, _ = panel
    p.bind_to_path(str(real_image))
    p._current = Recipe(exposure=.25, temperature=.1, shadows=.1, vibrance=.1)
    measurements = _measure_modify(p, qapp, 3)
    assert p._canvas_recipe == p._current
    assert len(measurements["modify_preview"]["samples_ms"]) == 3
    assert len(measurements["modify_full_compute"]["samples_ms"]) == 3
    assert measurements["modify_reduced_ready"] is None
    assert measurements["modify_preview"]["median_ms"] >= measurements["modify_full_compute"]["median_ms"]
