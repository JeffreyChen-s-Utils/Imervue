"""Pins the state a freshly constructed ``PuppetCanvas`` starts from.

Every attribute the constructor seeds, the widget flags, the surface format
(stencil, plus alpha in pet mode), the pet-mode translucency attributes, and
that constructing a canvas leaves the process-wide default surface format as
it found it — so splitting ``__init__`` cannot drop or alter any of it.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat

from _qt_skip import pytestmark  # noqa: E402,F401
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.physics import PhysicsEngine

_DEFAULTS = {
    "_document": None, "_draw_list": [], "_texture_cache": {}, "_zoom": 1.0,
    "_pan_x": 0.0, "_pan_y": 0.0, "_user_view_locked": False, "_panning": False,
    "_pan_anchor": (0.0, 0.0), "_parameter_values": {}, "_active_expressions": [],
    "_active_pose": {}, "_deformed_vertices": {}, "_visibility": {}, "_part_opacity": {},
    "_drawable_opacity": {}, "_drawable_tint": {}, "_selected_deformer": None,
    "_physics_outputs": {}, "_mesh_edit_enabled": False, "_mesh_edit_target": None,
    "_checker_texture": None, "_pet_shadow_texture": None, "_pet_shadow_enabled": False,
    "_pet_shadow_opacity": 1.0, "_pet_shadow_scale": 1.0, "_drawable_buffers": {},
}
_PET_ATTRS = (Qt.WidgetAttribute.WA_TranslucentBackground,
              Qt.WidgetAttribute.WA_NoSystemBackground,
              Qt.WidgetAttribute.WA_AlwaysStackOnTop)


@pytest.fixture
def make_canvas(qapp):
    made = []

    def _make(**kwargs):
        canvas = PuppetCanvas(**kwargs)
        made.append(canvas)
        return canvas

    yield _make
    for canvas in made:
        canvas.deleteLater()


def test_seeded_attributes(make_canvas):
    canvas = make_canvas()
    assert {name: getattr(canvas, name) for name in _DEFAULTS} == _DEFAULTS
    assert isinstance(canvas._physics, PhysicsEngine)  # noqa: SLF001
    assert canvas._pet_mode is False  # noqa: SLF001


def test_widget_flags(make_canvas):
    canvas = make_canvas()
    assert canvas.hasMouseTracking()
    assert canvas.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert not any(canvas.testAttribute(a) for a in _PET_ATTRS)


def test_surface_format(make_canvas):
    normal = make_canvas().format()
    pet = make_canvas(pet_mode=True).format()
    assert normal.stencilBufferSize() == 8
    assert pet.stencilBufferSize() == 8 and pet.alphaBufferSize() == 8


def test_pet_mode_translucency(make_canvas):
    canvas = make_canvas(pet_mode=True)
    assert canvas._pet_mode is True  # noqa: SLF001
    assert all(canvas.testAttribute(a) for a in _PET_ATTRS)


def test_default_surface_format_is_restored(make_canvas):
    before = QSurfaceFormat.defaultFormat()
    make_canvas(pet_mode=True)
    after = QSurfaceFormat.defaultFormat()
    assert (after.stencilBufferSize(), after.alphaBufferSize()) == (
        before.stencilBufferSize(), before.alphaBufferSize())


def test_instances_do_not_share_state(make_canvas):
    a, b = make_canvas(), make_canvas()
    a._parameter_values["x"] = 1.0  # noqa: SLF001
    assert b._parameter_values == {}  # noqa: SLF001
    assert a._physics is not b._physics  # noqa: SLF001
