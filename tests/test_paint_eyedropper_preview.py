"""Tests for the eyedropper hover preview in the status bar."""
from __future__ import annotations

import pytest

from Imervue.paint import tool_state as ts
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict

from _qt_skip import pytestmark  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_segment_absent_for_non_eyedropper_tool(workspace):
    workspace.state().set_tool("brush")
    workspace._on_hover_changed(10, 10)  # noqa: SLF001
    line = workspace._status.currentMessage()  # noqa: SLF001
    assert "#" not in line


def test_segment_present_for_eyedropper_with_hover(workspace):
    """Painting a known colour onto the active layer and hovering
    that pixel must surface the colour as a hex segment."""
    layer = workspace.canvas().document().active_layer()
    layer.image[10, 20, :3] = (200, 100, 50)
    layer.image[10, 20, 3] = 255
    workspace.state().set_tool("eyedropper")
    workspace._on_hover_changed(20, 10)  # noqa: SLF001
    line = workspace._status.currentMessage()  # noqa: SLF001
    # The hex segment encodes (200, 100, 50) — verifies the
    # eyedropper sample lands on the painted pixel.
    assert "#C86432" in line


def test_segment_dropped_when_cursor_leaves_canvas(workspace):
    workspace.state().set_tool("eyedropper")
    workspace._on_hover_changed(20, 10)  # noqa: SLF001
    workspace._on_hover_changed(-1, -1)  # noqa: SLF001
    line = workspace._status.currentMessage()  # noqa: SLF001
    # Hover gone → no x/y, no eyedrop segment.
    assert "#" not in line


def test_sample_returns_none_for_off_canvas_hover(workspace):
    """Out-of-range hover never panics — sampling clips to canvas."""
    h, w = workspace.canvas().document().shape
    sampled = workspace._sample_eyedropper_at((w + 5, h + 5))  # noqa: SLF001
    assert sampled is None


def test_sample_falls_back_to_active_layer_when_sample_all_off(workspace):
    """The default eyedropper mode reads the active layer; the
    preview must mirror that so the user gets the same colour they
    would commit on click."""
    layer = workspace.canvas().document().active_layer()
    layer.image[5, 5, :3] = (123, 45, 67)
    layer.image[5, 5, 3] = 255
    workspace.state().eyedropper_sample_all_layers = False
    sampled = workspace._sample_eyedropper_at((5, 5))  # noqa: SLF001
    assert sampled == (123, 45, 67)


def test_sample_uses_composite_when_sample_all_layers_on(workspace):
    """Toggling sample-all-layers must route the preview through
    the document composite — same source the click commit will
    use, so the displayed hex value matches what gets committed."""
    document = workspace.canvas().document()
    layer = document.active_layer()
    layer.image[7, 7, :3] = (10, 20, 30)
    layer.image[7, 7, 3] = 255
    workspace.state().eyedropper_sample_all_layers = True
    sampled = workspace._sample_eyedropper_at((7, 7))  # noqa: SLF001
    assert sampled is not None
    # Composite of single opaque layer == the layer itself.
    assert sampled == (10, 20, 30)
