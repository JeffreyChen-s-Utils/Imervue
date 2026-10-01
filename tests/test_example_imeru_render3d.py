"""Imeru's Blender driver (examples/puppet/imeru/render3d.py): what reaches Blender, and the load."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

_MODULE = Path(__file__).resolve().parents[1] / "examples" / "puppet" / "imeru" / "render3d.py"


def _load():
    spec = importlib.util.spec_from_file_location("imeru_render3d", _MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r3d = _load()


def test_the_cache_and_plain_layer_names_pass_through():
    args = r3d.checked_arguments(r3d.CACHE, ("bangs", "face_shadowed", "hand_open_l"))
    assert args == [str(r3d.CACHE.resolve()), "bangs", "face_shadowed", "hand_open_l"]


def test_an_output_folder_outside_the_example_is_refused(tmp_path):
    with pytest.raises(ValueError, match="inside"):
        r3d.checked_arguments(tmp_path, ())
    with pytest.raises(ValueError, match="inside"):
        r3d.checked_arguments(r3d.HERE / ".." / "render", ())


@pytest.mark.parametrize("name", ["--python-expr", "face;rm", "Face", "../face", ""])
def test_anything_but_a_plain_layer_name_is_refused(name):
    with pytest.raises(ValueError, match="layer names"):
        r3d.checked_arguments(r3d.CACHE, (name,))


def test_downsampling_averages_with_premultiplied_alpha():
    block = np.zeros((2, 2, 4), np.uint8)
    block[0, 0] = (255, 0, 0, 255)
    out = r3d._downsample(block)
    assert out.shape == (1, 1, 4)
    assert tuple(out[0, 0]) == (255, 0, 0, 64)


def test_a_shadow_layer_keeps_only_pixels_the_pass_darkened_inside_the_box():
    lit = np.full((4, 4, 4), 200, np.uint8)
    shadowed = lit.copy()
    shadowed[:, :2, :3] = 120
    out = r3d.shadow_layer(lit, shadowed, bottom=1)
    assert out[..., 3].nonzero()[0].max() == 1
    assert (out[:2, :2, 3] == 200).all() and not out[:, 2:, 3].any()
    assert tuple(out[0, 0, :3]) == (120, 120, 120)
