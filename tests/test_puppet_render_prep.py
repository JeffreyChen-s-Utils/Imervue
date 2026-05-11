"""Tests for the Qt-free render-prep helpers in
``plugins/puppet/render_prep.py`` — sorting drawables for paint, mapping
texture references, fit-to-window math, and screen→image inverse.
"""
from __future__ import annotations

import numpy as np
import pytest

from puppet.document import Drawable, PuppetDocument
from puppet.render_prep import (
    build_draw_list,
    collect_required_textures,
    fit_view,
    screen_to_image,
)


def _drawable(id_: str, draw_order: int, texture: str = "textures/x.png") -> Drawable:
    return Drawable(
        id=id_,
        texture=texture,
        vertices=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        indices=[0, 1, 2],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        draw_order=draw_order,
    )


# ---------------------------------------------------------------------------
# build_draw_list
# ---------------------------------------------------------------------------


def test_build_draw_list_orders_by_draw_order_ascending():
    doc = PuppetDocument()
    doc.drawables = [
        _drawable("a", draw_order=10),
        _drawable("b", draw_order=0),
        _drawable("c", draw_order=5),
    ]
    cmds = build_draw_list(doc)
    assert [c.drawable_id for c in cmds] == ["b", "c", "a"]


def test_build_draw_list_breaks_ties_by_array_order():
    doc = PuppetDocument()
    doc.drawables = [
        _drawable("first", draw_order=5),
        _drawable("second", draw_order=5),
    ]
    cmds = build_draw_list(doc)
    assert [c.drawable_id for c in cmds] == ["first", "second"]


def test_build_draw_list_converts_arrays_to_correct_dtypes():
    doc = PuppetDocument()
    doc.drawables = [_drawable("a", 0)]
    cmd = build_draw_list(doc)[0]
    assert cmd.vertices.dtype == np.float32
    assert cmd.uvs.dtype == np.float32
    assert cmd.indices.dtype == np.uint32


def test_build_draw_list_preserves_blend_mode_and_opacity():
    doc = PuppetDocument()
    d = _drawable("a", 0)
    d.blend_mode = "additive"
    d.opacity = 0.5
    doc.drawables = [d]
    cmd = build_draw_list(doc)[0]
    assert cmd.blend_mode == "additive"
    assert cmd.opacity == pytest.approx(0.5)


def test_build_draw_list_handles_empty_document():
    assert build_draw_list(PuppetDocument()) == []


# ---------------------------------------------------------------------------
# collect_required_textures
# ---------------------------------------------------------------------------


def test_collect_required_textures_dedupes():
    doc = PuppetDocument()
    doc.drawables = [
        _drawable("a", 0, texture="textures/face.png"),
        _drawable("b", 1, texture="textures/face.png"),
        _drawable("c", 2, texture="textures/body.png"),
    ]
    assert collect_required_textures(doc) == {
        "textures/face.png", "textures/body.png",
    }


def test_collect_required_textures_empty_document():
    assert collect_required_textures(PuppetDocument()) == set()


# ---------------------------------------------------------------------------
# fit_view
# ---------------------------------------------------------------------------


def test_fit_view_centres_puppet_in_canvas():
    zoom, px, py = fit_view(canvas_size=(1000, 1000), puppet_size=(500, 500))
    # 5% margin → zoom ~1.9
    assert zoom == pytest.approx(1.9, abs=0.01)
    # Centred in the remaining space
    assert px == pytest.approx((1000 - 500 * zoom) / 2)
    assert py == pytest.approx((1000 - 500 * zoom) / 2)


def test_fit_view_picks_smaller_axis_to_avoid_clipping():
    """A wide canvas with a tall puppet: zoom is bound by the tighter
    axis (vertical) so nothing clips."""
    zoom, _, _ = fit_view(canvas_size=(2000, 500), puppet_size=(100, 100))
    assert zoom == pytest.approx((500 / 100) * 0.95)


def test_fit_view_returns_safe_defaults_for_degenerate_inputs():
    assert fit_view(canvas_size=(0, 100), puppet_size=(100, 100)) == (1.0, 0.0, 0.0)
    assert fit_view(canvas_size=(100, 100), puppet_size=(0, 0)) == (1.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# screen_to_image
# ---------------------------------------------------------------------------


def test_screen_to_image_inverts_translate_and_scale():
    # Setup: zoom 2x, pan (50, 30). Image-space (10, 20) maps to
    # screen-space (50 + 10*2, 30 + 20*2) = (70, 70).
    zoom, pan_x, pan_y = 2.0, 50.0, 30.0
    sx, sy = 70.0, 70.0
    ix, iy = screen_to_image(sx, sy, zoom, pan_x, pan_y)
    assert ix == pytest.approx(10.0)
    assert iy == pytest.approx(20.0)


def test_screen_to_image_zero_zoom_returns_origin():
    assert screen_to_image(100.0, 100.0, 0.0, 0.0, 0.0) == (0.0, 0.0)
