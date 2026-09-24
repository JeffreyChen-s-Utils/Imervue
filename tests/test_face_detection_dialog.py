"""Qt smoke tests for the face detection dialog's detect step.

``detect_faces`` and the recipe store are monkeypatched, so neither OpenCV nor
the real recipe file is involved.
"""
from __future__ import annotations

import numpy as np
import pytest

from Imervue.gui import face_detection_dialog as mod
from Imervue.image.face_detection import FaceDetectorUnavailableError, FaceTag
from Imervue.image.recipe import Recipe
from Imervue.multi_language.language_wrapper import language_wrapper

_ARR = np.zeros((8, 8, 3), dtype=np.uint8)


@pytest.fixture
def dialog(qapp, monkeypatch, sample_png):
    monkeypatch.setattr(mod.recipe_store, "get_for_path", lambda _p: Recipe())
    dlg = mod.FaceDetectionDialog(None, str(sample_png))
    yield dlg
    dlg.deleteLater()


def _raise(exc):
    def _detect(_arr):
        raise exc
    return _detect


@pytest.mark.parametrize("exc", [
    FaceDetectorUnavailableError("OpenCV 5.0.0 has no Haar face cascade"),
    ImportError("No module named 'cv2'"),
])
def test_missing_detector_shows_the_opencv4_hint(dialog, monkeypatch, exc):
    monkeypatch.setattr(mod, "detect_faces", _raise(exc))
    dialog._detect(_ARR)
    expected = language_wrapper.language_word_dict.get(
        "face_needs_opencv4", mod._NEEDS_OPENCV4)
    assert dialog._status.text() == expected
    assert "opencv-python<5" in dialog._status.text()
    assert dialog._list.count() == 0


def test_other_failures_show_the_error_text(dialog, monkeypatch):
    monkeypatch.setattr(mod, "detect_faces", _raise(RuntimeError("failed to load Haar cascade")))
    dialog._detect(_ARR)
    assert dialog._status.text() == "failed to load Haar cascade"


def test_detections_are_listed_once(dialog, monkeypatch):
    monkeypatch.setattr(mod, "detect_faces", lambda _arr: [FaceTag(1, 2, 3, 4)])
    dialog._detect(_ARR)
    dialog._detect(_ARR)
    assert dialog._list.count() == 1


def test_every_language_translates_the_hint():
    from Imervue.multi_language import (
        chinese,
        english,
        japanese,
        korean,
        traditional_chinese,
    )
    for module in (chinese, english, japanese, korean, traditional_chinese):
        words = next(v for k, v in vars(module).items()
                     if k.endswith("_word_dict") and isinstance(v, dict))
        assert "opencv-python<5" in words["face_needs_opencv4"], module.__name__
