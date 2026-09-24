"""The labelled output / profile path rows of the single-image tool dialogs.

For each dialog this pins the row's widgets (label text, the dialog's own
path edit with the stretch, the Browse button), the edit's default path, and
what Browse does: open the save / open file dialog with the right title,
starting path and filter, write a picked path into the edit and keep the edit
on cancel — the contract the shared ``dialog_rows`` builders have to keep.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QFileDialog, QLabel, QLineEdit, QPushButton

from Imervue.multi_language.language_wrapper import language_wrapper

_IMAGES = "Images (*.png *.jpg *.tif)"

# module, class, edit attribute, label, file-dialog method, title, filter,
# default-path suffix ("" = empty edit, None = not derived from the image),
# and the file dialog's start path (``_EDIT`` = the edit's current text)
_EDIT = object()
_CASES = [
    ("auto_straighten_dialog", "AutoStraightenDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "_straight.png", _EDIT),
    ("clone_stamp_dialog", "CloneStampDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "_clone.png", _EDIT),
    ("crop_straighten_dialog", "CropStraightenDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "_crop.png", _EDIT),
    ("healing_brush_dialog", "HealingBrushDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "_healed.png", _EDIT),
    ("lens_correction_dialog", "LensCorrectionDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "_lens.png", _EDIT),
    ("noise_sharpen_dialog", "NoiseSharpenDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "_nr.png", _EDIT),
    ("sky_replace_dialog", "SkyReplaceDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", "Images (*.png *.tif)", "_sky.png", _EDIT),
    ("print_layout_dialog", "PrintLayoutDialog", "_out_edit", "Output PDF:",
     "getSaveFileName", "Output PDF", "PDF (*.pdf)", None, _EDIT),
    ("soft_proof_dialog", "SoftProofDialog", "_profile_edit", "ICC profile:",
     "getOpenFileName", "ICC profile", "ICC profiles (*.icc *.icm)", "", ""),
    ("focus_stack_dialog", "FocusStackDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", "Images (*.jpg *.png *.tif)", "", "stacked.jpg"),
    ("hdr_merge_dialog", "HdrMergeDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "", "merged.png"),
    ("panorama_dialog", "PanoramaDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", "Images (*.jpg *.png *.tif)", "", "panorama.jpg"),
    ("stack_blend_dialog", "StackBlendDialog", "_out_edit", "Output:",
     "getSaveFileName", "Output", _IMAGES, "", "stacked.png"),
]

_VIEWER_ONLY = {"PrintLayoutDialog", "FocusStackDialog", "HdrMergeDialog",
                "PanoramaDialog", "StackBlendDialog"}


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "photo.png"
    Image.fromarray(np.full((24, 32, 3), 128, dtype=np.uint8)).save(path)
    return str(path)


def _build(module, cls, image):
    dialog_cls = getattr(importlib.import_module(f"Imervue.gui.{module}"), cls)
    if cls in _VIEWER_ONLY:
        return dialog_cls(None)
    return dialog_cls(None, image)


def _find_layout(layout, widget):
    """The (possibly nested) layout that directly holds ``widget``."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is widget:
            return layout
        if item.layout() is not None:
            found = _find_layout(item.layout(), widget)
            if found is not None:
                return found
    return None


@pytest.mark.parametrize(
    ("module", "cls", "edit_attr", "label", "method", "title", "file_filter", "suffix",
     "start_dir"),
    _CASES, ids=[c[1] for c in _CASES])
def test_path_row(qapp, monkeypatch, image, module, cls, edit_attr, label, method,
                  title, file_filter, suffix, start_dir):
    dialog = _build(module, cls, image)
    try:
        edit = getattr(dialog, edit_attr)
        assert isinstance(edit, QLineEdit)
        row = _find_layout(dialog.layout(), edit)
        assert row is not None
        widgets = [row.itemAt(i).widget() for i in range(row.count())]
        assert len(widgets) == 3
        assert isinstance(widgets[0], QLabel) and widgets[0].text() == label
        assert widgets[1] is edit
        assert isinstance(widgets[2], QPushButton) and widgets[2].text() == "Browse..."
        assert [row.stretch(i) for i in range(3)] == [0, 1, 0]

        if suffix is None:
            assert edit.text() == str(Path.home() / "print_sheet.pdf")
        elif suffix == "":
            assert edit.text() == ""
        else:
            assert edit.text() == str(Path(image).with_name(f"photo{suffix}"))

        start = edit.text()
        calls = []
        answers = iter([("C:/picked/out.png", ""), ("", "")])

        def fake(parent, caption, directory, filt):
            calls.append((parent, caption, directory, filt))
            return next(answers)

        monkeypatch.setattr(QFileDialog, method, staticmethod(fake))
        widgets[2].click()
        assert edit.text() == "C:/picked/out.png"
        widgets[2].click()
        assert edit.text() == "C:/picked/out.png"
        expected_dir = start if start_dir is _EDIT else start_dir
        assert calls[0] == (dialog, title, expected_dir, file_filter)
    finally:
        dialog.deleteLater()
