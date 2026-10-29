"""Contracts of the write-side MCP handlers in ``Imervue.mcp_server.tools_edit``.

Pins what the existing handler tests leave open: the exact pixels and summary of
every effect tool (against a direct call of the pure image function with the
documented defaults), the shared validation helpers' boundaries and messages, and
that every handler stays importable from ``tools_edit`` as the same object the
``tools`` facade and the tool definitions hand out.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from PIL import Image

from Imervue.image import curves
from Imervue.image.auto_color_balance import AutoBalanceOptions, auto_balance
from Imervue.image.channel_mixer import ChannelMixerOptions, apply_channel_mixer
from Imervue.image.clahe import apply_clahe
from Imervue.image.colormap import apply_colormap
from Imervue.image.defringe import apply_defringe
from Imervue.image.dehaze import dehaze
from Imervue.image.detail_equalizer import apply_detail_equalizer
from Imervue.image.distort import distort
from Imervue.image.dither import ordered_dither
from Imervue.image.emboss import apply_emboss
from Imervue.image.false_color import false_color
from Imervue.image.film_grain import FilmGrainOptions, apply_film_grain
from Imervue.image.film_negative import apply_film_negative
from Imervue.image.filmic_tonemap import apply_filmic_tonemap
from Imervue.image.frosted_glass import frosted_glass
from Imervue.image.glow import apply_glow
from Imervue.image.gradient_map import GradientMapOptions, apply_gradient_map
from Imervue.image.graduated_density import apply_graduated_density
from Imervue.image.kaleidoscope import kaleidoscope
from Imervue.image.lens_correction import LensCorrectionOptions, apply_lens_correction
from Imervue.image.levels import LevelsOptions, apply_levels
from Imervue.image.local_contrast import apply_clarity, apply_texture
from Imervue.image.pixel_sort import pixel_sort
from Imervue.image.polar import polar_distort
from Imervue.image.posterize import PosterizeOptions, apply_posterize
from Imervue.image.solarize import apply_solarize
from Imervue.image.split_toning import apply_split_toning
from Imervue.image.tone_equalizer import apply_tone_equalizer
from Imervue.image.velvia import apply_velvia
from Imervue.mcp_server import tools, tools_edit
from Imervue.mcp_server.tool_defs_edit import EDIT_TOOL_DEFINITIONS
from Imervue.mcp_server.tool_support import load_rgba_array

_PNG = "src.png"


@pytest.fixture
def src(tmp_path):
    """A small RGBA gradient with varied alpha, saved as PNG."""
    ys, xs = np.mgrid[0:18, 0:22]
    arr = np.zeros((18, 22, 4), dtype=np.uint8)
    arr[..., 0] = (xs * 11) % 256
    arr[..., 1] = (ys * 14) % 256
    arr[..., 2] = ((xs + ys) * 7) % 256
    arr[..., 3] = 255
    arr[2:5, 3:7, 3] = 90
    path = tmp_path / _PNG
    Image.fromarray(arr, "RGBA").save(path)
    return path


def _mixer(red=(1.0, 0.0, 0.0), green=(0.0, 1.0, 0.0), blue=(0.0, 0.0, 1.0),
           offsets=(0.0, 0.0, 0.0), monochrome=False):
    return ChannelMixerOptions(
        enabled=True, red=list(red), green=list(green), blue=list(blue),
        offsets=list(offsets), monochrome=monochrome,
    )


def _curve(points):
    return curves.CurveOptions(enabled=True, per_channel={"rgb": points})


# (handler name, kwargs, the pure call the handler must reproduce)
_EFFECT_CASES = [
    ("solarize_image", {}, lambda a: apply_solarize(a, 0.5, 1.0)),
    ("solarize_image", {"threshold": 0.3, "mix": 0.5},
     lambda a: apply_solarize(a, 0.3, 0.5)),
    ("glow_image", {}, lambda a: apply_glow(a, 0.5, 15, 0.0)),
    ("velvia_image", {}, lambda a: apply_velvia(a, 1.0, 0.5)),
    ("emboss_image", {}, lambda a: apply_emboss(a, 135.0, 45.0, 1.0, True)),
    ("film_negative_image", {}, lambda a: apply_film_negative(a, None, 1.0)),
    ("defringe_image", {}, lambda a: apply_defringe(a, 1.0, 0.1, "purple")),
    ("graduated_density_image", {},
     lambda a: apply_graduated_density(a, 0.0, 1.0, 0.5, 0.0)),
    ("filmic_tonemap_image", {},
     lambda a: apply_filmic_tonemap(a, 0.0, 4.0, 1.0, 1.0, "reinhard")),
    ("tone_equalizer_image", {},
     lambda a: apply_tone_equalizer(a, (0.0, 0.0, 0.0, 0.0, 0.0), 12)),
    ("tone_equalizer_image", {"zone_gains": [1, 0, 0, -1, 0], "smoothing": 4},
     lambda a: apply_tone_equalizer(a, (1.0, 0.0, 0.0, -1.0, 0.0), 4)),
    ("detail_equalizer_image", {},
     lambda a: apply_detail_equalizer(a, (1.0, 1.0, 1.0, 1.0))),
    ("detail_equalizer_image", {"band_gains": [2, 1]},
     lambda a: apply_detail_equalizer(a, (2.0, 1.0))),
    ("colormap_image", {}, lambda a: apply_colormap(a, "viridis")),
    ("false_color_image", {}, false_color),
    ("dither_image", {}, lambda a: ordered_dither(a, 2)),
    ("split_toning_image", {},
     lambda a: apply_split_toning(a, 210.0, 0.0, 45.0, 0.0, 0.0)),
    ("pixel_sort_image", {}, lambda a: pixel_sort(a, 60, 200, vertical=False)),
    ("polar_image", {}, lambda a: polar_distort(a, True, False)),
    ("kaleidoscope_image", {}, lambda a: kaleidoscope(a, 6, None, 0.0)),
    ("kaleidoscope_image", {"segments": 4, "angle_deg": 30},
     lambda a: kaleidoscope(a, 4, None, math.radians(30.0))),
    ("frosted_glass_image", {}, lambda a: frosted_glass(a, 4, 0)),
    ("clahe_image", {}, lambda a: apply_clahe(a, 2.0, 8)),
    ("local_contrast_image", {"clarity": 0.4, "texture": 0.3},
     lambda a: apply_texture(apply_clarity(a, 0.4), 0.3)),
    ("posterize_image", {},
     lambda a: apply_posterize(a, PosterizeOptions(enabled=True, levels=4))),
    ("gradient_map_image", {}, lambda a: apply_gradient_map(
        a, GradientMapOptions(enabled=True, intensity=1.0, perceptual=False))),
    ("film_grain_image", {}, lambda a: apply_film_grain(a, FilmGrainOptions(
        enabled=True, intensity=0.25, size=1, monochrome=True, seed=0))),
    ("dehaze_image", {}, lambda a: dehaze(a, 0.5)),
    ("distort_image", {}, lambda a: distort(a, "swirl", 0.5)),
    ("levels_image", {}, lambda a: apply_levels(
        a, LevelsOptions(enabled=True, black=0, white=255, gamma=1.0))),
    ("auto_color_balance_image", {}, lambda a: auto_balance(a, AutoBalanceOptions(
        method="percentile_stretch", intensity=1.0, percentile=1.0, retinex_radius=24))),
    ("channel_mixer_image", {}, lambda a: apply_channel_mixer(a, _mixer())),
    ("channel_mixer_image",
     {"red": [0.3, 0.5, 0.2], "offsets": [5, 0, 0], "monochrome": True},
     lambda a: apply_channel_mixer(
         a, _mixer(red=(0.3, 0.5, 0.2), offsets=(5.0, 0.0, 0.0), monochrome=True))),
    ("curve_image", {}, lambda a: curves.apply_curves(
        a, _curve(curves.s_curve_preset(0.15)))),
    ("curve_image", {"preset": "lift_shadows", "strength": 0.25},
     lambda a: curves.apply_curves(a, _curve(curves.lift_shadows_preset(0.25)))),
    ("curve_image", {"preset": "compress_highlights", "strength": 0.3},
     lambda a: curves.apply_curves(a, _curve(curves.compress_highlights_preset(0.3)))),
    ("lens_correction_image", {"k1": 0.1, "vignette": 0.2},
     lambda a: apply_lens_correction(a, LensCorrectionOptions(
         k1=0.1, vignette=0.2, ca_red=0.0, ca_blue=0.0))),
]


@pytest.mark.parametrize(
    "name, kwargs, expected",
    _EFFECT_CASES,
    ids=[f"{case[0]}-{i}" for i, case in enumerate(_EFFECT_CASES)],
)
def test_effect_handler_matches_pure_call(src, tmp_path, name, kwargs, expected):
    dst = tmp_path / "out.png"
    summary = getattr(tools_edit, name)(str(src), str(dst), **kwargs)
    want = expected(load_rgba_array(src))
    with Image.open(dst) as saved:
        got = np.asarray(saved.convert("RGBA"))
    np.testing.assert_array_equal(got, want)
    assert summary == {
        "source": str(src),
        "destination": str(dst),
        "width": int(want.shape[1]),
        "height": int(want.shape[0]),
        "size_bytes": dst.stat().st_size,
    }


def test_effect_handler_flattens_alpha_for_jpeg(src, tmp_path):
    dst = tmp_path / "out.jpg"
    tools_edit.dither_image(str(src), str(dst))
    with Image.open(dst) as saved:
        assert saved.mode == "RGB"


def test_effect_handler_rejects_missing_source_and_parent(src, tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        tools_edit.velvia_image(str(tmp_path / "nope.png"), str(tmp_path / "o.png"))
    missing = tmp_path / "no_dir" / "o.png"
    with pytest.raises(ValueError, match=r"^destination parent .* does not exist$"):
        tools_edit.velvia_image(str(src), str(missing))


def test_curve_image_unknown_preset_message(src, tmp_path):
    with pytest.raises(ValueError) as info:
        tools_edit.curve_image(str(src), str(tmp_path / "o.png"), preset="zigzag")
    assert str(info.value) == (
        "unknown curve preset 'zigzag'; expected one of "
        "('s_curve', 'lift_shadows', 'compress_highlights')"
    )
    assert not (tmp_path / "o.png").exists()


# --- shared helpers ---------------------------------------------------------


@pytest.mark.parametrize("color, expected", [
    (None, (1, 2, 3)),
    ([10, 20, 30], (10, 20, 30)),
    ((300, -5, 255), (255, 0, 255)),
    ([True, 0, 0], (1, 0, 0)),
])
def test_validated_rgb_triplet_accepts(color, expected):
    assert tools_edit._validated_rgb_triplet(color, (1, 2, 3)) == expected


@pytest.mark.parametrize("color", [[1, 2], [1, 2, 3, 4], [1.0, 2, 3], "abc", 7, {}])
def test_validated_rgb_triplet_rejects(color):
    with pytest.raises(ValueError) as info:
        tools_edit._validated_rgb_triplet(color, (0, 0, 0))
    assert str(info.value) == "color must be a list of three integers 0-255"


def test_guard_output_pixels_boundary():
    tools_edit._guard_output_pixels(10_000, 10_000)
    with pytest.raises(ValueError) as info:
        tools_edit._guard_output_pixels(10_001, 10_000)
    assert str(info.value) == (
        "output 10001x10000 exceeds the 100000000-pixel limit"
    )


@pytest.mark.parametrize("dims, expected", [
    ((40, 20, 10, 5), (10, 5)),
    ((40, 20, 10, None), (10, 5)),
    ((40, 20, None, 4), (8, 4)),
    ((1000, 1, 1, None), (1, 1)),
    ((1, 1000, None, 1), (1, 1)),
])
def test_resize_dims(dims, expected):
    assert tools_edit._resize_dims(*dims) == expected


def test_validated_destination(tmp_path):
    assert tools_edit._validated_destination(str(tmp_path / "x.png")) == tmp_path / "x.png"
    with pytest.raises(ValueError) as info:
        tools_edit._validated_destination(str(tmp_path / "a" / "x.png"))
    assert str(info.value) == f"destination parent {tmp_path / 'a'} does not exist"


# --- geometry / overlay handlers --------------------------------------------


def test_rotate_unknown_operation_message(src, tmp_path):
    with pytest.raises(ValueError) as info:
        tools_edit.rotate_image(str(src), str(tmp_path / "o.png"), "spin")
    assert str(info.value) == (
        "operation must be one of ['flip_horizontal', 'flip_vertical', "
        "'rotate_180', 'rotate_270', 'rotate_90'], got 'spin'"
    )


@pytest.mark.parametrize("operation, transpose", [
    ("rotate_90", Image.Transpose.ROTATE_270),
    ("rotate_180", Image.Transpose.ROTATE_180),
    ("rotate_270", Image.Transpose.ROTATE_90),
    ("flip_horizontal", Image.Transpose.FLIP_LEFT_RIGHT),
    ("flip_vertical", Image.Transpose.FLIP_TOP_BOTTOM),
])
def test_rotate_pixels(src, tmp_path, operation, transpose):
    dst = tmp_path / "o.png"
    summary = tools_edit.rotate_image(str(src), str(dst), operation)
    with Image.open(src) as original, Image.open(dst) as saved:
        want = np.asarray(original.transpose(transpose))
        np.testing.assert_array_equal(np.asarray(saved), want)
    assert summary == {
        "source": str(src), "destination": str(dst), "operation": operation,
        "width": want.shape[1], "height": want.shape[0],
        "size_bytes": dst.stat().st_size,
    }


def test_crop_pixels_and_messages(src, tmp_path):
    dst = tmp_path / "o.png"
    summary = tools_edit.crop_image(str(src), str(dst), x=2, y=3, width=5, height=4)
    with Image.open(src) as original, Image.open(dst) as saved:
        np.testing.assert_array_equal(
            np.asarray(saved), np.asarray(original)[3:7, 2:7])
    assert summary == {
        "source": str(src), "destination": str(dst), "width": 5, "height": 4,
        "size_bytes": dst.stat().st_size,
    }
    with pytest.raises(ValueError) as info:
        tools_edit.crop_image(str(src), str(dst), x=20, y=0, width=5, height=4)
    assert str(info.value) == "crop box (20,0,5x4) exceeds image 22x18"


def test_resize_guard_message_and_summary(src, tmp_path):
    dst = tmp_path / "o.png"
    with pytest.raises(ValueError) as info:
        tools_edit.resize_image(str(src), str(dst), width=100_000)
    assert str(info.value) == "output 100000x81818 exceeds the 100000000-pixel limit"
    summary = tools_edit.resize_image(str(src), str(dst), height=9)
    assert summary == {
        "source": str(src), "destination": str(dst), "width": 11, "height": 9,
        "size_bytes": dst.stat().st_size,
    }


def test_watermark_messages(src, tmp_path):
    dst = str(tmp_path / "o.png")
    with pytest.raises(ValueError) as info:
        tools_edit.apply_watermark(str(src), dst, "  ")
    assert str(info.value) == "text must be a non-empty string"
    with pytest.raises(ValueError) as info:
        tools_edit.apply_watermark(str(src), dst, "hi", corner="middle")
    assert str(info.value) == (
        "corner must be one of ['bottom-left', 'bottom-right', 'center', "
        "'top-left', 'top-right'], got 'middle'"
    )
    summary = tools_edit.apply_watermark(str(src), dst, "hi", corner="center")
    assert summary["corner"] == "center"
    assert set(summary) == {"source", "destination", "size_bytes", "corner"}


def test_frame_clamps_negative_border(src, tmp_path):
    dst = tmp_path / "o.png"
    summary = tools_edit.apply_frame(str(src), str(dst), border=-4, bottom_extra=-1)
    assert (summary["width"], summary["height"]) == (22, 18)


def test_collage_progress_and_messages(src, tmp_path):
    class _Recorder:
        def __init__(self):
            self.calls = []

        def report(self, index, *, total, message):
            self.calls.append((index, total, message))

    dst = tmp_path / "o.png"
    rec = _Recorder()
    summary = tools_edit.build_collage(
        [str(src)] * 3, str(dst), columns=2, cell_width=10, cell_height=8,
        gap=2, margin=1, progress=rec,
    )
    assert rec.calls == [
        (1, 3, "loaded 1/3"), (2, 3, "loaded 2/3"), (3, 3, "loaded 3/3"),
    ]
    assert summary == {
        "destination": str(dst), "image_count": 3, "columns": 2,
        "width": 1 * 2 + 2 * 10 + 2, "height": 1 * 2 + 2 * 8 + 2,
        "size_bytes": dst.stat().st_size,
    }
    with pytest.raises(ValueError) as info:
        tools_edit.build_collage([str(src)] * 201, str(dst))
    assert str(info.value) == "collage supports at most 200 images"
    with pytest.raises(ValueError) as info:
        tools_edit.build_collage("x", str(dst))
    assert str(info.value) == "sources must be a non-empty list of image paths"


# --- import surface ---------------------------------------------------------


def test_every_edit_handler_is_the_same_object_everywhere():
    for definition in EDIT_TOOL_DEFINITIONS:
        handler = getattr(tools_edit, definition["name"])
        assert definition["handler"] is handler
        assert getattr(tools, definition["name"]) is handler
    assert len(EDIT_TOOL_DEFINITIONS) == 36
