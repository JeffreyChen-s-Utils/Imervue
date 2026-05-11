"""Tests for the PSD → puppet multi-layer import path.

Builds a synthetic 3-layer PSD via the existing
``Imervue.paint.psd_io.save_psd`` writer (so no checked-in binary
fixture) and asserts the puppet document that comes out: drawable
count, drawable bounding boxes, texture dedupe, draw_order, and
standard-parameter seeding.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint.document import PaintDocument
from Imervue.paint.psd_io import save_psd
from puppet.psd_import import puppet_from_psd


def _make_psd_with_three_layers(path) -> None:
    """Synthetic PSD: 32×32 canvas, three opaque squares at known
    positions on three layers named ``head``, ``eye_l``, ``eye_r``."""
    doc = PaintDocument()
    base = np.zeros((32, 32, 4), dtype=np.uint8)
    base[8:24, 8:24, :3] = (200, 100, 50)
    base[8:24, 8:24, 3] = 255
    doc.load_image(base)
    # Active background layer name defaults to something — rename it
    doc.layers()[0].name = "head"
    eye_l = doc.add_layer(name="eye_l")
    eye_l.image[10:14, 10:14, :3] = (50, 50, 200)
    eye_l.image[10:14, 10:14, 3] = 255
    eye_r = doc.add_layer(name="eye_r")
    eye_r.image[10:14, 18:22, :3] = (200, 50, 50)
    eye_r.image[10:14, 18:22, 3] = 255
    save_psd(doc, path)


def test_psd_import_makes_one_drawable_per_visible_layer(tmp_path):
    psd = tmp_path / "rig.psd"
    _make_psd_with_three_layers(psd)
    doc = puppet_from_psd(psd)
    assert len(doc.drawables) == 3
    assert {d.id for d in doc.drawables} == {"head", "eye_l", "eye_r"}


def test_psd_import_preserves_canvas_size(tmp_path):
    psd = tmp_path / "rig.psd"
    _make_psd_with_three_layers(psd)
    doc = puppet_from_psd(psd)
    assert doc.size == (32, 32)


def test_psd_import_crops_drawable_to_alpha_bbox(tmp_path):
    psd = tmp_path / "rig.psd"
    _make_psd_with_three_layers(psd)
    doc = puppet_from_psd(psd)
    eye_l = next(d for d in doc.drawables if d.id == "eye_l")
    xs = [v[0] for v in eye_l.vertices]
    ys = [v[1] for v in eye_l.vertices]
    assert (min(xs), max(xs)) == (10.0, 14.0)
    assert (min(ys), max(ys)) == (10.0, 14.0)


def test_psd_import_draw_order_follows_layer_stack(tmp_path):
    """Bottom of layer stack draws first (lowest draw_order); top
    draws last. The synthetic PSD adds ``head`` then ``eye_l`` then
    ``eye_r``, so that's the back-to-front order."""
    psd = tmp_path / "rig.psd"
    _make_psd_with_three_layers(psd)
    doc = puppet_from_psd(psd)
    by_id = {d.id: d for d in doc.drawables}
    assert by_id["head"].draw_order < by_id["eye_l"].draw_order
    assert by_id["eye_l"].draw_order < by_id["eye_r"].draw_order


def test_psd_import_seeds_standard_parameters_by_default(tmp_path):
    psd = tmp_path / "rig.psd"
    _make_psd_with_three_layers(psd)
    doc = puppet_from_psd(psd)
    ids = {p.id for p in doc.parameters}
    assert "ParamAngleX" in ids
    assert "ParamBreath" in ids


def test_psd_import_can_skip_standard_parameters(tmp_path):
    psd = tmp_path / "rig.psd"
    _make_psd_with_three_layers(psd)
    doc = puppet_from_psd(
        psd, seed_standard_parameters=False, enable_auto_rig=False,
    )
    assert doc.parameters == []


def test_psd_import_dedupes_layers_with_same_sanitized_name(tmp_path):
    """Two layers named identically (after sanitisation) must still
    produce two distinct drawables — the second gets a suffix."""
    psd = tmp_path / "dupes.psd"
    doc = PaintDocument()
    base = np.zeros((16, 16, 4), dtype=np.uint8)
    base[2:6, 2:6, :3] = (100, 100, 100)
    base[2:6, 2:6, 3] = 255
    doc.load_image(base)
    doc.layers()[0].name = "part"
    second = doc.add_layer(name="part")
    second.image[8:12, 8:12, :3] = (50, 50, 50)
    second.image[8:12, 8:12, 3] = 255
    save_psd(doc, psd)
    out = puppet_from_psd(psd)
    ids = [d.id for d in out.drawables]
    assert len(set(ids)) == len(ids)   # all unique
    assert "part" in ids


def test_psd_import_skips_fully_transparent_layers(tmp_path):
    psd = tmp_path / "blank.psd"
    doc = PaintDocument()
    base = np.zeros((16, 16, 4), dtype=np.uint8)
    base[2:6, 2:6, :3] = (100, 100, 100)
    base[2:6, 2:6, 3] = 255
    doc.load_image(base)
    doc.layers()[0].name = "real"
    ghost = doc.add_layer(name="ghost")
    # Don't paint anything — fully transparent layer
    _ = ghost
    save_psd(doc, psd)
    out = puppet_from_psd(psd)
    assert [d.id for d in out.drawables] == ["real"]


def test_psd_import_raises_when_no_visible_layer_has_pixels(tmp_path):
    psd = tmp_path / "all_empty.psd"
    doc = PaintDocument()
    base = np.zeros((16, 16, 4), dtype=np.uint8)
    doc.load_image(base)
    save_psd(doc, psd)
    with pytest.raises(ValueError):
        puppet_from_psd(psd)


def test_psd_import_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        puppet_from_psd("does/not/exist.psd")
