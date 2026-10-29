"""Explicit save controls preserve originals and report actual destinations."""
from __future__ import annotations

import os

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from Imervue.gui import annotation_file_actions
from Imervue.gui.develop_save_controls import is_source_destination
from Imervue.gui.annotation_models import Annotation
from Imervue.image.recipe import Recipe
from tests import test_develop_panel as shared

main_window = shared.main_window
panel = shared.panel
real_image = shared.real_image


def test_save_controls_show_original_and_explicit_actions(panel, real_image):
    p, _ = panel
    p.bind_to_path(str(real_image))
    assert p._btn_ann_save.isEnabled()
    assert p._btn_save_copy.isEnabled()
    assert str(real_image) in p._save_destination.text()
    assert p._btn_ann_save.text() != p._btn_save_copy.text()
    assert p._crop_consequence.text()
    assert p._crop_apply_btn.text() != "Apply"
    p.bind_to_path(None)
    assert not p._btn_ann_save.isEnabled()
    assert not p._btn_save_copy.isEnabled()
    assert not p._crop_apply_btn.isEnabled()


def test_raw_controls_require_copy(panel, tmp_path, monkeypatch):
    p, _ = panel
    path = tmp_path / "photo.cr2"
    path.write_bytes(b"camera raw")
    monkeypatch.setattr(p, "_decode_source", lambda _path: Image.new("RGBA", (20, 30)))
    p.bind_to_path(str(path))
    assert not p._btn_ann_save.isEnabled()
    assert not p._crop_apply_btn.isEnabled()
    assert p._btn_save_copy.isEnabled()
    assert str(path) in p._save_destination.text()


def test_copy_button_writes_full_result_and_keeps_edits(panel, real_image, tmp_path, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(real_image))
    before = real_image.read_bytes()
    p._current = Recipe(exposure=.5)
    annotation = Annotation(kind="rect", points=[(2, 2), (18, 18)], filled=True)
    p._canvas.set_annotations([annotation])
    target = str(tmp_path / "copy.png")
    monkeypatch.setattr(annotation_file_actions, "ask_save_as_path", lambda *_: target)
    QTest.mouseClick(p._btn_save_copy, Qt.MouseButton.LeftButton)
    assert real_image.read_bytes() == before
    assert p.current_recipe().exposure == .5
    assert p._canvas.get_annotations() == [annotation]
    assert Image.open(target).size == Image.open(real_image).size
    assert target in p._save_result.text()
    assert not p._save_result.isHidden()


@pytest.mark.parametrize("alias", [False, True])
def test_copy_rejects_original_and_hardlink(panel, real_image, tmp_path, monkeypatch, alias):
    p, _ = panel
    p.bind_to_path(str(real_image))
    target = real_image
    if alias:
        target = tmp_path / "alias.png"
        os.link(real_image, target)
    before = real_image.read_bytes()
    p._current = Recipe(brightness=.4)
    monkeypatch.setattr(annotation_file_actions, "ask_save_as_path", lambda *_: str(target))
    messages = []
    monkeypatch.setattr(p, "_toast", lambda *args: messages.append(args))
    p._save_copy()
    assert real_image.read_bytes() == before
    assert p.current_recipe().brightness == .4
    assert messages[-1][1] == "warning"
    assert p._save_result.isHidden()


def test_copy_write_failure_preserves_working_pixels(panel, real_image, tmp_path, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(real_image))
    p._current = Recipe(exposure=.3)
    assert p._ensure_full_canvas()
    expected = np.array(p._canvas.get_base_pil())
    monkeypatch.setattr(annotation_file_actions, "ask_save_as_path", lambda *_: str(tmp_path / "copy.png"))
    def fail(*_args):
        raise OSError("disk full")
    monkeypatch.setattr(annotation_file_actions, "write_annotated", fail)
    messages = []
    monkeypatch.setattr(p, "_toast", lambda *args: messages.append(args))
    p._save_copy()
    np.testing.assert_array_equal(p._canvas.get_base_pil(), expected)
    assert p.current_recipe().exposure == .3
    assert messages[-1][1] == "warning"
    assert "copy.png" in p._save_result.text()
    assert not p._save_result.isHidden()


def test_destination_comparison_for_new_path(tmp_path):
    assert is_source_destination(str(tmp_path / "a.png"), str(tmp_path / "a.png"))
    assert not is_source_destination(str(tmp_path / "copy.png"), str(tmp_path / "a.png"))


def test_crop_success_reports_path(panel, real_image):
    p, _ = panel
    p.bind_to_path(str(real_image))
    p._canvas._crop_rect = (0, 0, 20, 20)
    p._apply_crop()
    assert str(real_image) in p._save_result.text()


def test_cancelled_copy_keeps_result_hidden(panel, real_image, monkeypatch):
    p, _ = panel
    p.bind_to_path(str(real_image))
    monkeypatch.setattr(annotation_file_actions, "ask_save_as_path", lambda *_: "")
    p._save_copy()
    assert p._save_result.isHidden()
