"""The Brush dock's Scatter, Colour jitter and Follow tilt reach the stroke.

They were saved in ``BrushSettings`` and presets but no stroke read them
(``progress.md`` #48). ``BrushTool`` now passes them in ``BrushStrokeOptions``,
``BrushStroke`` applies ``Imervue.paint.brush_random`` per dab, and such
strokes stay on the CPU because the GPU session stamps one colour and one
kernel per stroke.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_engine import BrushStroke, BrushStrokeOptions
from Imervue.paint.canvas import PointerEvent
from Imervue.paint.gpu_brush import _gpu_supported
from Imervue.paint.tools import painting
from Imervue.paint.tools.painting import BrushTool

_RED = (200, 20, 20)


def _canvas(size: int = 96) -> np.ndarray:
    return np.zeros((size, size, 4), dtype=np.uint8)


def _stroke(canvas: np.ndarray, *, seed: int = 7, **options) -> np.ndarray:
    """Paint a horizontal line across the middle of *canvas* and return it."""
    stroke = BrushStroke(BrushStrokeOptions(color=_RED, size=6, opacity=1.0, hardness=1.0,
                                            seed=seed, **options))
    mid = canvas.shape[0] / 2
    stroke.begin(canvas, 10.0, mid)
    stroke.extend(canvas, 50.0, mid)
    stroke.end(canvas, 86.0, mid)
    return canvas


def _painted_rows(canvas: np.ndarray) -> np.ndarray:
    return np.nonzero(canvas[..., 3].any(axis=1))[0]


def _extent(canvas: np.ndarray) -> tuple[int, int]:
    """(height, width) of the painted area."""
    ys, xs = np.nonzero(canvas[..., 3])
    return int(np.ptp(ys)) + 1, int(np.ptp(xs)) + 1


def test_without_randomisation_the_line_keeps_its_width_and_colour():
    canvas = _stroke(_canvas())
    rows = _painted_rows(canvas)
    assert rows.max() - rows.min() <= 7
    painted = canvas[canvas[..., 3] > 0][:, :3]
    assert {tuple(c) for c in painted} == {_RED}


def test_scatter_spreads_dabs_off_the_line():
    plain = _painted_rows(_stroke(_canvas()))
    scattered = _painted_rows(_stroke(_canvas(), scatter=1.0))
    assert scattered.max() - scattered.min() > plain.max() - plain.min() + 2


def test_the_same_seed_repeats_the_stroke_exactly():
    first = _stroke(_canvas(), scatter=0.8, color_jitter=0.8)
    again = _stroke(_canvas(), scatter=0.8, color_jitter=0.8)
    other = _stroke(_canvas(), seed=8, scatter=0.8, color_jitter=0.8)
    np.testing.assert_array_equal(first, again)
    assert not np.array_equal(first, other)


def test_colour_jitter_varies_the_dab_colour():
    canvas = _stroke(_canvas(), color_jitter=1.0)
    solid = canvas[canvas[..., 3] == 255][:, :3]
    assert len({tuple(c) for c in solid}) > 3


@pytest.mark.parametrize(("tilt", "wider"), [((1.0, 0.0), "across"), ((0.0, 1.0), "down")])
def test_follow_tilt_narrows_the_dab_across_the_lean(tilt, wider):
    canvas = _canvas()
    stroke = BrushStroke(BrushStrokeOptions(color=_RED, size=31, opacity=1.0, hardness=1.0,
                                            follow_tilt=True))
    stroke.set_tilt(*tilt)
    stroke.begin(canvas, 48.0, 48.0)
    height, width = _extent(canvas)
    assert (width > height + 8) if wider == "across" else (height > width + 8)


def test_without_follow_tilt_the_tilt_is_ignored():
    canvas = _canvas()
    stroke = BrushStroke(BrushStrokeOptions(color=_RED, size=31, opacity=1.0, hardness=1.0))
    stroke.set_tilt(1.0, 0.0)
    stroke.begin(canvas, 48.0, 48.0)
    height, width = _extent(canvas)
    assert abs(height - width) <= 1


def test_pixel_art_keeps_its_square_under_tilt():
    canvas = _canvas()
    stroke = BrushStroke(BrushStrokeOptions(color=_RED, size=9, opacity=1.0, hardness=1.0,
                                            follow_tilt=True, pixel_art=True))
    stroke.set_tilt(1.0, 0.0)
    stroke.begin(canvas, 48.0, 48.0)
    assert _extent(canvas) == (9, 9)


def test_scatter_in_pixel_art_stays_on_whole_pixels():
    canvas = _canvas()
    stroke = BrushStroke(BrushStrokeOptions(color=_RED, size=3, opacity=1.0, hardness=1.0,
                                            scatter=1.0, pixel_art=True, seed=3))
    stroke.begin(canvas, 20.0, 48.0)
    stroke.end(canvas, 70.0, 48.0)
    assert set(np.unique(canvas[..., 3])) <= {0, 255}


def test_the_end_taper_keeps_each_dab_s_own_colour():
    canvas = _stroke(_canvas(), color_jitter=1.0, taper_end_dabs=4)
    assert len({tuple(c) for c in canvas[canvas[..., 3] > 0][:, :3]}) > 3


@pytest.mark.parametrize("option", [{"scatter": 0.2}, {"color_jitter": 0.2}, {"follow_tilt": True}])
def test_randomised_strokes_stay_on_the_cpu(option):
    plain = BrushStrokeOptions(color=_RED, size=6, opacity=1.0, hardness=1.0)
    assert _gpu_supported(plain)
    assert not _gpu_supported(BrushStrokeOptions(color=_RED, size=6, opacity=1.0, hardness=1.0,
                                                 **option))


# --- BrushTool hands the settings and the pen tilt over ----------------------

def _event(phase: str, x: float, tilt: tuple[float, float]) -> PointerEvent:
    return PointerEvent(phase=phase, x=x, y=32.0, button=1, modifiers=0, pressure=1.0,
                        tilt_x=tilt[0], tilt_y=tilt[1])


class _RecordingStroke:
    def __init__(self, options):
        self.options = options
        self.tilts: list[tuple[float, float]] = []

    def set_tilt(self, tilt_x, tilt_y):
        self.tilts.append((tilt_x, tilt_y))

    def begin(self, *_args):
        pass

    def extend(self, *_args):
        pass

    def end(self, *_args):
        pass

    stroke_damage = None


@pytest.fixture
def made(monkeypatch):
    strokes: list[_RecordingStroke] = []

    def make(options, *, prefer_gpu=True):
        strokes.append(_RecordingStroke(options))
        return strokes[-1]

    monkeypatch.setattr("Imervue.paint.gpu_brush.make_brush_stroke", make)
    monkeypatch.setattr(painting.BrushTool, "_collect_damage", lambda _self: None)
    return strokes


@pytest.mark.parametrize("follow", [True, False])
def test_the_brush_tool_passes_the_settings_and_the_tilt(made, follow):
    state = ts.load_tool_state()
    state.set_foreground((10, 20, 30))
    state.set_brush(scatter=0.4, color_jitter=0.3, follow_tilt=follow)
    tool = BrushTool(state)
    tool.handle(_event("press", 10.0, (0.5, 0.0)), np.zeros((64, 64, 4), np.uint8))
    tool.handle(_event("move", 20.0, (0.0, 0.7)), np.zeros((64, 64, 4), np.uint8))
    (stroke,) = made
    assert (stroke.options.scatter, stroke.options.color_jitter) == (0.4, 0.3)
    assert stroke.options.follow_tilt is follow
    assert stroke.tilts == ([(0.5, 0.0), (0.0, 0.7)] if follow else [])
