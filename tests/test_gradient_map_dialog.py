"""Smoke test for the gradient-map dialog's perceptual toggle.

Construction only (reads the recipe store, writes nothing); the effect maths
live in test_gradient_map / test_gradient_perceptual.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gui.gradient_map_dialog import GradientMapDialog, open_gradient_map_dialog


def test_dialog_has_perceptual_checkbox_default_off(qapp):
    # Stub viewer (not a QWidget) -> dialog uses parent=None; a path with no
    # stored recipe yields the default options.
    dlg = GradientMapDialog(SimpleNamespace(), "no_such_image.png")
    assert dlg._perceptual.isChecked() is False
    dlg._perceptual.setChecked(True)
    assert dlg._perceptual.isChecked() is True


def test_open_guard_no_images_is_noop():
    viewer = SimpleNamespace(model=SimpleNamespace(images=[]), current_index=-1)
    open_gradient_map_dialog(viewer)  # NOSONAR
