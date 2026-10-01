"""Imeru's face shading (examples/puppet/imeru/face_shadow.py): the SDF face map and its rings."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_MODULE = Path(__file__).resolve().parents[1] / "examples" / "puppet" / "imeru" / "face_shadow.py"
CX = 512.0


def _load():
    spec = importlib.util.spec_from_file_location("imeru_face_shadow", _MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fs = _load()


@pytest.fixture(scope="module")
def face() -> np.ndarray:
    """A small oval face, centred like hers, on a canvas cut short below the chin."""
    h, w = 800, 1024
    ys, xs = np.mgrid[0:h, 0:w]
    inside = ((xs + 0.5 - CX) / 70.0) ** 2 + ((ys + 0.5 - 640.0) / 90.0) ** 2 <= 1.0
    return np.where(inside, 255, 0).astype(np.uint8)


@pytest.fixture(scope="module")
def angles(face) -> np.ndarray:
    return fs.threshold_map(face, CX)


def test_face_rows_measure_the_half_width_of_every_row(face):
    rows = fs.face_rows(face, CX)
    assert min(rows) == 550 and max(rows) == 729
    assert rows[640] == pytest.approx(70.0, abs=1.0)
    assert rows[551] < rows[640]


def test_the_shadow_line_runs_from_the_face_edge_to_its_middle(face):
    rows = fs.face_rows(face, CX)
    at_zero = dict((y, x) for x, y in fs.shadow_line(rows, CX, 0.0))
    at_right_angle = dict((y, x) for x, y in fs.shadow_line(rows, CX, 90.0))
    assert at_zero[640] == pytest.approx(CX + rows[640])
    assert at_right_angle[640] == pytest.approx(CX)
    assert fs.shadow_line(rows, CX, -10.0) == fs.shadow_line(rows, CX, 0.0)


def test_the_cheek_holds_the_light_longer_than_the_temple(face):
    rows = {y: 70.0 for y in (520, 640)}
    line = dict((y, x) for x, y in fs.shadow_line(rows, CX, 45.0))
    assert line[640] > line[520]


def test_every_key_shadow_contains_the_one_before(face):
    masks = fs.key_masks(face, CX)
    assert len(masks) == len(fs.KEY_ANGLES)
    for smaller, larger in zip(masks, masks[1:], strict=False):
        assert not (smaller & ~larger).any()
    assert masks[-1][640, int(CX) + 30] and not masks[-1][640, int(CX) - 30]


def test_a_drawn_key_shadow_can_give_light_back_but_the_nested_one_keeps_it(face):
    rows = fs.face_rows(face, CX)
    drawn = [fs.key_mask(face.shape, rows, CX, a) for a in fs.KEY_ANGLES]
    given_back = drawn[3] & ~drawn[4]
    assert given_back.any()
    assert not (given_back & ~fs.key_masks(face, CX)[4]).any()


def test_the_nose_shadow_appears_past_thirty_degrees_and_the_lit_patch_between_fifty_and_85():
    assert fs._nose(30.0, CX) is None and fs._nose(45.0, CX) is not None
    assert fs._lit_triangle(50.0, CX) is None and fs._lit_triangle(85.0, CX) is None
    small, large = fs._lit_triangle(80.0, CX), fs._lit_triangle(55.0, CX)
    span = lambda tri: max(x for x, _ in tri) - min(x for x, _ in tri)  # noqa: E731
    assert span(small) < span(large)


def test_the_map_holds_light_angles_and_grows_toward_the_far_edge(face, angles):
    inside = face > 0
    assert angles[inside].min() >= 0.0 and angles[inside].max() <= 90.0
    assert (angles[~inside] == 90.0).all()
    row = angles[640]
    assert row[int(CX) - 40] == 90.0
    assert row[int(CX) + 60] < row[int(CX) + 40] < row[int(CX) + 10]


def test_a_pixel_between_two_key_shadows_gets_an_angle_between_them(face, angles):
    first, second = fs.key_masks(face, CX)[1:3]
    ys, xs = np.nonzero(second & ~first & (face > 0))
    values = angles[ys, xs]
    assert len(values) > 0
    assert (values >= fs.KEY_ANGLES[1]).all() and (values <= fs.KEY_ANGLES[2]).all()
    assert values.min() < values.max()


def test_the_rings_split_the_face_by_side(face):
    layers = fs.shade_layers(face, CX)
    assert list(layers) == list(fs.RINGS)
    xs = np.nonzero(layers["face_shade_0"][..., 3].any(axis=0))[0]
    assert len(xs) and xs.max() < CX
    for name in ("face_shade_1", "face_shade_2", "face_shade_3", "face_shade_4"):
        xs = np.nonzero(layers[name][..., 3].any(axis=0))[0]
        # the nose shadow wraps a couple of pixels past the centre line
        assert len(xs) and xs.min() >= CX - 3, name
    for layer in layers.values():
        assert not layer[..., 3][face == 0].any()
        assert tuple(layer[..., :3][layer[..., 3] > 0][0]) == fs.SHADE


def test_at_rest_only_a_thin_crescent_is_in_shadow(face):
    layers = fs.shade_layers(face, CX)
    rest = np.maximum(layers["face_shade_1"][..., 3], layers["face_shade_2"][..., 3])
    share = (rest > 127).sum() / (face > 0).sum()
    assert 0.0 < share < 0.15


def test_ring_opacity_fades_each_ring_in_across_its_part_of_the_turn():
    for name, (start, end) in fs.RINGS.items():
        stops = fs.ring_opacity(name)
        assert [s["value"] for s in stops] == pytest.approx(
            [start / fs.TURN_DEGREES, end / fs.TURN_DEGREES])
        assert all(-1.0 <= s["value"] <= 1.0 for s in stops)
        alphas = [s["alpha"] for s in stops]
        assert alphas == ([1.0, 0.0] if name == "face_shade_0" else [0.0, 1.0])


def test_rest_falls_on_a_ring_boundary():
    assert fs.RINGS["face_shade_2"][1] == 0.0 == fs.RINGS["face_shade_3"][0]
    assert fs.RINGS["face_shade_0"][1] == pytest.approx(-fs.REST_ANGLE)


def test_the_hair_shadow_is_the_hair_moved_along_the_light_and_kept_on_the_face():
    face = np.zeros((60, 60), np.uint8)
    face[:, 20:] = 255
    hair = np.zeros((60, 60), np.uint8)
    hair[10:20, 10:30] = 255
    shadow = fs.hair_shadow(face, hair, offset=(5, 14))
    alpha = shadow[..., 3]
    ys, xs = np.nonzero(alpha)
    assert (ys.min(), ys.max()) == (24, 33)
    assert (xs.min(), xs.max()) == (20, 34)
    assert not alpha[:, :20].any()


def test_merge_keeps_the_stronger_coverage():
    a = fs._layer(np.array([[1.0, 0.2]]))
    b = fs._layer(np.array([[0.5, 0.6]]))
    assert fs.merge(a, b)[..., 3].tolist() == [[255, 153]]
