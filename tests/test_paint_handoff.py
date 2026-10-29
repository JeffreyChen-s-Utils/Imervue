"""Handoff selects canonical pixels and never replaces an existing Paint document."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox

from Imervue.gui import paint_handoff as handoff
from Imervue.gui.annotation_models import Annotation, bake
from Imervue.image.recipe import Recipe
from tests import test_develop_panel as shared

main_window = shared.main_window
panel = shared.panel
real_image = shared.real_image


@pytest.mark.parametrize("has_annotations", [False, True])
def test_dialog_keyboard_choice_and_annotation_policy(qapp, has_annotations):
    dialog = handoff.PaintHandoffDialog("photo.png", has_annotations=has_annotations)
    dialog.show()
    assert dialog.source.currentData() == handoff.PaintSource.ORIGINAL
    assert not dialog.include_annotations()
    QTest.keyClick(dialog.source, Qt.Key.Key_Down)
    assert dialog.source.currentData() == handoff.PaintSource.CURRENT
    assert dialog.include_annotations() == has_annotations
    if has_annotations:
        QTest.keyClick(dialog.annotations, Qt.Key.Key_Space)
        assert not dialog.include_annotations()
    buttons = dialog.findChild(QDialogButtonBox)
    QTest.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Open), Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted
    dialog.deleteLater()


def test_current_handoff_uses_working_full_resolution_and_annotations(
        panel, tmp_path, pump_until):
    p, _ = panel
    path = tmp_path / "large.png"
    Image.new("RGBA", (1600, 1200), (30, 60, 90, 255)).save(path)
    p.bind_to_path(str(path))
    p._current = Recipe(exposure=.5)
    p._request_preview(final=False)
    pump_until(lambda: p._preview.is_idle)
    assert p._canvas._base_qimg.width() < 1600
    annotation = Annotation(kind="rect", points=[(0, 0), (20, 20)], filled=True)
    p._canvas.set_annotations([annotation])
    expected = p._current.apply(np.array(p._decoded_source))
    pixels = handoff.current_pixels(str(path), p, include_annotations=False)
    np.testing.assert_array_equal(pixels, expected)
    with_annotations = handoff.current_pixels(str(path), p, include_annotations=True)
    np.testing.assert_array_equal(with_annotations,
        np.array(bake(Image.fromarray(expected), [annotation])))
    assert p._current.exposure == .5
    assert p._canvas.get_annotations() == [annotation]


def test_current_handoff_without_panel_applies_saved_geometry_and_exposure(tmp_path, monkeypatch):
    path = str(tmp_path / "source.png")
    image = np.full((30, 20, 4), (20, 40, 60, 255), dtype=np.uint8)
    Image.fromarray(image).save(path)
    recipe = Recipe(rotate_steps=1, flip_h=True, crop=(1, 2, 12, 10), exposure=.5)
    monkeypatch.setattr(handoff, "recipe_store", SimpleNamespace(get_for_path=lambda _: recipe))
    pixels = handoff.current_pixels(path, None, include_annotations=False)
    np.testing.assert_array_equal(pixels, recipe.apply(image))
    assert pixels.shape == (10, 12, 4)


def test_failed_canonical_render_does_not_open_paint(panel, real_image, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(real_image))
    monkeypatch.setattr(p, "_ensure_full_canvas", lambda: False)
    errors = []
    window = SimpleNamespace(toast=SimpleNamespace(error=errors.append))
    handoff.open_current_result(window, str(real_image), p, include_annotations=True)
    assert len(errors) == 1


def test_handoff_preserves_existing_paint_document_and_marks_copy_dirty(monkeypatch):
    from tests.test_main_window_paint import _Window
    window = _Window(["source.png"])
    workspace = window.paint_workspace
    original, old_stack = workspace.document, workspace.stack
    original.active_layer().image[1, 1] = (42, 42, 42, 255)
    old_stack.commit()
    dirty = []
    workspace.canvas = lambda: workspace.document
    workspace._set_tab_dirty = lambda canvas, value: dirty.append((canvas, value))
    pixels = np.full((18, 24, 4), 123, dtype=np.uint8)
    monkeypatch.setattr(handoff, "current_pixels", lambda *args, **kwargs: pixels)
    handoff.open_current_result(window, "source.png", None, include_annotations=False)
    assert workspace.documents[0] is original
    assert workspace.document is not original
    np.testing.assert_array_equal(workspace.document.layer_at(0).image, pixels)
    assert old_stack.undo()
    np.testing.assert_array_equal(original.active_layer().image[1, 1], (0, 0, 0, 0))
    assert dirty == [(workspace.document, True)]
    assert window.tab_changes == [2]


def test_missing_source_reports_error_without_creating_document(tmp_path):
    errors = []
    window = SimpleNamespace(toast=SimpleNamespace(error=errors.append))
    handoff.open_current_result(window, str(tmp_path / "missing.png"), None,
                                include_annotations=False)
    assert len(errors) == 1


def test_no_current_image_has_actionable_message():
    messages = []
    window = SimpleNamespace(viewer=SimpleNamespace(
        model=SimpleNamespace(images=[]), current_index=0),
        toast=SimpleNamespace(info=messages.append))
    handoff.choose_paint_handoff(window)
    assert messages


def test_annotation_choice_settles_geometry_before_advertising_overlays(panel, real_image):
    p, _ = panel
    p.bind_to_path(str(real_image))
    p._canvas.set_annotations([Annotation(kind="rect", points=[(1, 1), (10, 10)])])
    p._current = Recipe(crop=(0, 0, 10, 10))
    assert not handoff.available_annotations(str(real_image), p)
    assert p._canvas.get_base_pil().size == (10, 10)
    assert not p._canvas.get_annotations()


def test_annotation_choice_handles_unavailable_render(panel, real_image, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(real_image))
    annotation = Annotation(kind="rect", points=[(1, 1), (10, 10)])
    p._canvas.set_annotations([annotation])
    monkeypatch.setattr(p, "_ensure_full_canvas", lambda: False)
    assert not handoff.available_annotations(str(real_image), p)
    assert p._canvas.get_annotations() == [annotation]


@pytest.mark.parametrize("result", [QDialog.DialogCode.Accepted, QDialog.DialogCode.Rejected])
def test_chooser_original_and_cancel_preserve_legacy_action(qapp, monkeypatch, result):
    from PySide6.QtWidgets import QMainWindow
    window = QMainWindow()
    window.viewer = SimpleNamespace(model=SimpleNamespace(images=["photo.png"]), current_index=0)
    calls = []
    window._bind_paint_workspace_to_current_image = lambda **kwargs: calls.append(kwargs["path"])
    monkeypatch.setattr(handoff.PaintHandoffDialog, "exec", lambda _: result)
    handoff.choose_paint_handoff(window)
    assert calls == (["photo.png"] if result == QDialog.DialogCode.Accepted else [])
    window.deleteLater()
