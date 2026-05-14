"""Tests for the parameter-driven visibility sweep in
``cubism_native_convert``.

The Cubism Core DLL isn't redistributable, so we stub the parts of
:class:`CubismModel` and :class:`DrawableInfo` that
:func:`_attach_visibility_keys` actually reads. The function under
test is otherwise pure-Python and exercising it without the DLL is
the only way it gets CI coverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import pytest

from Imervue.puppet.cubism_native_bridge import (
    CubismModel,
    DrawableInfo,
    ParameterInfo,
)
from Imervue.puppet.cubism_native_convert import _attach_visibility_keys
from Imervue.puppet.document import Drawable, PuppetDocument


@dataclass
class _FakeModel:
    """Stub matching the surface ``_attach_visibility_keys`` calls.

    Holds a script of ``{(param_index, value): list[bool]}`` mapping a
    parameter sample to the visibility flags the model would report.
    The defaults list lets the fake detect which parameter index
    deviated when the converter calls ``set_parameter_values`` —
    necessary because Cubism min / default / max can all be 0.0
    legitimately, so the deviation is signal, not the raw value.
    """

    visibility_script: dict[tuple[int, float], list[bool]]
    parameter_count_value: int
    drawable_count_value: int
    defaults: list[float] = field(default_factory=list)
    rest_visibility: list[bool] | None = None
    _last_sample: tuple[int, float] | None = None

    def parameter_count(self) -> int:
        return self.parameter_count_value

    def drawable_count(self) -> int:
        return self.drawable_count_value

    def set_parameter_values(self, values):
        self._last_sample = None
        for i, (v, d) in enumerate(zip(values, self.defaults, strict=False)):
            if v != d:
                self._last_sample = (i, float(v))
                return

    def update(self):
        return None

    def visibility_flags(self) -> list[bool]:
        fallback = (
            list(self.rest_visibility)
            if self.rest_visibility is not None
            else [True] * self.drawable_count_value
        )
        if self._last_sample is None:
            return fallback
        return self.visibility_script.get(self._last_sample, fallback)


def _make_doc_with_n(n: int) -> PuppetDocument:
    doc = PuppetDocument(size=(64, 64))
    for i in range(n):
        doc.drawables.append(Drawable(
            id=f"d{i}", texture="textures/x.png",
            vertices=[(0.0, 0.0)], indices=[], uvs=[(0.0, 0.0)],
            draw_order=0, visible=True, opacity=1.0,
        ))
    return doc


# ---------------------------------------------------------------------------
# No-change skip
# ---------------------------------------------------------------------------


def test_no_visibility_change_emits_no_keys():
    """A parameter whose drawables stay visible at every sample point
    must not contribute any opacity_keys entries."""
    doc = _make_doc_with_n(2)
    params = [ParameterInfo(id="P", minimum=-1.0, maximum=1.0, default=0.0)]
    drawables_rest = [
        DrawableInfo(
            id=f"d{i}", texture_index=0, draw_order=0, render_order=0,
            is_visible=True, opacity=1.0, blend_mode=0, constant_flags=0,
            vertex_count=1, index_count=0,
            positions=[0.0, 0.0], uvs=[0.0, 0.0],
            indices=[], mask_drawable_indices=[],
        )
        for i in range(2)
    ]
    model = _FakeModel(
        visibility_script={
            (0, -1.0): [True, True],
            (0, 1.0): [True, True],
        },
        parameter_count_value=1,
        drawable_count_value=2,
        defaults=[0.0],
        rest_visibility=[True, True],
    )
    _attach_visibility_keys(doc, cast(CubismModel, model), params, drawables_rest)
    assert all(d.opacity_keys is None for d in doc.drawables)


# ---------------------------------------------------------------------------
# Hidden-at-default, visible-at-max → fade-in curve
# ---------------------------------------------------------------------------


def test_hidden_default_visible_at_max_emits_fade_in_curve():
    """The wave-style case: an alternate-pose mesh is hidden at the
    parameter's default and pops visible at the parameter's max. The
    converter must emit a three-stop curve covering that transition
    and override the drawable's authored visible/opacity so the
    curve has authority over the renderer."""
    doc = _make_doc_with_n(1)
    # Mesh starts hidden — the converter wrote that based on rest IsVisible.
    doc.drawables[0].visible = False
    doc.drawables[0].opacity = 0.0
    params = [ParameterInfo(id="ParamPeace", minimum=0.0, maximum=1.0, default=0.0)]
    drawables_rest = [
        DrawableInfo(
            id="d0", texture_index=0, draw_order=0, render_order=0,
            is_visible=False, opacity=0.0, blend_mode=0, constant_flags=0,
            vertex_count=1, index_count=0,
            positions=[0.0, 0.0], uvs=[0.0, 0.0],
            indices=[], mask_drawable_indices=[],
        ),
    ]
    model = _FakeModel(
        visibility_script={
            (0, 1.0): [True],    # at max — mesh becomes visible
        },
        parameter_count_value=1,
        drawable_count_value=1,
        defaults=[0.0],
        rest_visibility=[False],   # hidden at rest matches DrawableInfo
    )
    _attach_visibility_keys(doc, cast(CubismModel, model), params, drawables_rest)
    d = doc.drawables[0]
    assert d.visible is True
    assert d.opacity == pytest.approx(1.0)
    assert d.opacity_keys is not None and len(d.opacity_keys) == 1
    key = d.opacity_keys[0]
    assert key["parameter"] == "ParamPeace"
    stops = key["stops"]
    assert len(stops) == 3
    # default-value stop carries alpha=0 (hidden at rest)
    default_stop = next(s for s in stops if s["value"] == pytest.approx(0.0))
    assert default_stop["alpha"] == pytest.approx(0.0)
    # max-value stop carries alpha=1 (visible when active)
    max_stop = next(s for s in stops if s["value"] == pytest.approx(1.0))
    assert max_stop["alpha"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Visible-at-default, hidden-at-extreme → fade-out curve
# ---------------------------------------------------------------------------


def test_visible_default_hidden_at_max_emits_fade_out_curve():
    """A drawable visible at rest that disappears when the parameter
    fires (e.g. an arm-down mesh that hides while the arm-up pose
    activates). The curve flips from 1.0 to 0.0 across the range."""
    doc = _make_doc_with_n(1)
    params = [ParameterInfo(id="P", minimum=-1.0, maximum=1.0, default=0.0)]
    drawables_rest = [
        DrawableInfo(
            id="d0", texture_index=0, draw_order=0, render_order=0,
            is_visible=True, opacity=1.0, blend_mode=0, constant_flags=0,
            vertex_count=1, index_count=0,
            positions=[0.0, 0.0], uvs=[0.0, 0.0],
            indices=[], mask_drawable_indices=[],
        ),
    ]
    model = _FakeModel(
        visibility_script={
            (0, -1.0): [True],   # still visible at min
            (0, 1.0): [False],   # hidden at max
        },
        parameter_count_value=1,
        drawable_count_value=1,
        defaults=[0.0],
        rest_visibility=[True],
    )
    _attach_visibility_keys(doc, cast(CubismModel, model), params, drawables_rest)
    stops = doc.drawables[0].opacity_keys[0]["stops"]
    by_value = {s["value"]: s["alpha"] for s in stops}
    assert by_value[-1.0] == pytest.approx(1.0)
    assert by_value[0.0] == pytest.approx(1.0)
    assert by_value[1.0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Multiple parameters per drawable accumulate as a list of curves
# ---------------------------------------------------------------------------


def test_multiple_params_accumulate_as_separate_curves():
    """One drawable may be gated by more than one parameter (face-cover
    AND peace-sign both might hide the original hand). Each visibility-
    changing parameter contributes its own entry — they don't collapse
    into a single curve."""
    doc = _make_doc_with_n(1)
    params = [
        ParameterInfo(id="A", minimum=0.0, maximum=1.0, default=0.0),
        ParameterInfo(id="B", minimum=0.0, maximum=1.0, default=0.0),
    ]
    drawables_rest = [
        DrawableInfo(
            id="d0", texture_index=0, draw_order=0, render_order=0,
            is_visible=False, opacity=0.0, blend_mode=0, constant_flags=0,
            vertex_count=1, index_count=0,
            positions=[0.0, 0.0], uvs=[0.0, 0.0],
            indices=[], mask_drawable_indices=[],
        ),
    ]
    model = _FakeModel(
        visibility_script={
            (0, 1.0): [True],
            (1, 1.0): [True],
        },
        parameter_count_value=2,
        drawable_count_value=1,
        defaults=[0.0, 0.0],
        rest_visibility=[False],
    )
    _attach_visibility_keys(doc, cast(CubismModel, model), params, drawables_rest)
    keys = doc.drawables[0].opacity_keys
    assert keys is not None and len(keys) == 2
    assert {k["parameter"] for k in keys} == {"A", "B"}


# ---------------------------------------------------------------------------
# Degenerate parameter ranges are skipped cleanly
# ---------------------------------------------------------------------------


def test_zero_range_parameter_is_skipped():
    """A parameter with min == max can't sweep — the converter must
    skip it cleanly without dividing by zero or emitting an empty
    curve."""
    doc = _make_doc_with_n(1)
    params = [ParameterInfo(id="P", minimum=0.5, maximum=0.5, default=0.5)]
    drawables_rest = [
        DrawableInfo(
            id="d0", texture_index=0, draw_order=0, render_order=0,
            is_visible=True, opacity=1.0, blend_mode=0, constant_flags=0,
            vertex_count=1, index_count=0,
            positions=[0.0, 0.0], uvs=[0.0, 0.0],
            indices=[], mask_drawable_indices=[],
        ),
    ]
    model = _FakeModel(
        visibility_script={},
        parameter_count_value=1,
        drawable_count_value=1,
        defaults=[0.5],
        rest_visibility=[True],
    )
    _attach_visibility_keys(doc, cast(CubismModel, model), params, drawables_rest)
    assert doc.drawables[0].opacity_keys is None
