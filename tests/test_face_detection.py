"""Tests for face detection."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from Imervue.image import face_detection as fd


def _haar_available() -> bool:
    try:
        fd._load_cascade()
    except (ImportError, RuntimeError):
        return False
    return True


requires_haar = pytest.mark.skipif(
    not _haar_available(), reason="needs OpenCV 4 with its Haar cascades",
)


class _FakeCascade:
    def __init__(self, *, empty: bool = False, readable: bool = True):
        self.xml = None
        self._empty = empty
        self._readable = readable

    def read(self, node) -> bool:
        self.xml = node
        return self._readable

    def empty(self) -> bool:
        return self._empty or self.xml is None

    @staticmethod
    def detectMultiScale(gray, **_kwargs):  # noqa: N802 - mirrors the cv2 name
        return [(0, 0, 10, 10), (5, 5, 30, 40)] if gray.any() else ()


class _FakeStorage:
    """``cv2.FileStorage`` reading from memory: its top node is the XML text itself."""

    def __init__(self, source: str, flags: int):
        assert flags == 4
        self._source = source

    def getFirstTopLevelNode(self):  # noqa: N802 - mirrors the cv2 name
        return self._source


def _fake_cv2(monkeypatch, *, classifier=_FakeCascade, data_dir=None):
    """Install a stand-in ``cv2`` whose Haar pieces the test controls."""
    cv2 = types.ModuleType("cv2")
    cv2.__version__ = "9.9.9"
    cv2.COLOR_RGB2GRAY = 7
    cv2.cvtColor = lambda arr, _code: arr[..., 0]
    cv2.FILE_STORAGE_READ, cv2.FILE_STORAGE_MEMORY = 0, 4
    cv2.FileStorage = _FakeStorage
    if classifier is not None:
        cv2.CascadeClassifier = classifier
    if data_dir is not None:
        cv2.data = types.SimpleNamespace(haarcascades=str(data_dir) + "/")
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    return cv2


@pytest.fixture
def cascade_dir(tmp_path):
    (tmp_path / fd._CASCADE_FILE).write_text("<opencv_storage/>", encoding="utf-8")
    return tmp_path


class TestLoadCascade:
    def test_loads_the_frontal_face_cascade(self, monkeypatch, cascade_dir):
        _fake_cv2(monkeypatch, data_dir=cascade_dir)
        cascade = fd._load_cascade()
        assert cascade.xml == "<opencv_storage/>"

    def test_no_classifier_is_unavailable(self, monkeypatch, cascade_dir):
        # OpenCV 5 without contrib: CascadeClassifier is gone.
        _fake_cv2(monkeypatch, classifier=None, data_dir=cascade_dir)
        with pytest.raises(fd.FaceDetectorUnavailableError, match="9.9.9"):
            fd._load_cascade()

    def test_missing_cascade_file_is_unavailable(self, monkeypatch, tmp_path):
        # OpenCV 5 contrib: the class exists but no wheel ships the XML files.
        _fake_cv2(monkeypatch, data_dir=tmp_path)
        with pytest.raises(fd.FaceDetectorUnavailableError):
            fd._load_cascade()

    def test_no_data_module_is_unavailable(self, monkeypatch):
        _fake_cv2(monkeypatch)
        with pytest.raises(fd.FaceDetectorUnavailableError):
            fd._load_cascade()

    def test_unreadable_cascade_is_a_plain_runtime_error(self, monkeypatch, cascade_dir):
        _fake_cv2(
            monkeypatch,
            classifier=lambda: _FakeCascade(empty=True),
            data_dir=cascade_dir,
        )
        with pytest.raises(RuntimeError, match="failed to load") as info:
            fd._load_cascade()
        assert not isinstance(info.value, fd.FaceDetectorUnavailableError)

    def test_a_cascade_opencv_cannot_parse_is_a_runtime_error(self, monkeypatch, cascade_dir):
        _fake_cv2(monkeypatch, classifier=lambda: _FakeCascade(readable=False),
                  data_dir=cascade_dir)
        with pytest.raises(RuntimeError, match="failed to load"):
            fd._load_cascade()

    def test_a_cascade_that_is_not_text_is_a_runtime_error(self, monkeypatch, tmp_path):
        (tmp_path / fd._CASCADE_FILE).write_bytes(b"\xff\xfe\x00")
        _fake_cv2(monkeypatch, data_dir=tmp_path)
        with pytest.raises(RuntimeError, match="failed to load"):
            fd._load_cascade()

    @requires_haar
    def test_opencv_under_a_non_ascii_folder_still_loads(self, monkeypatch, tmp_path):
        """cv2.CascadeClassifier(path) came back empty for such a path on Windows."""
        import shutil

        import cv2
        folder = tmp_path / "使用者"
        folder.mkdir()
        shutil.copy(Path(cv2.data.haarcascades) / fd._CASCADE_FILE, folder)
        monkeypatch.setattr(cv2.data, "haarcascades", str(folder) + os.sep)
        assert not fd._load_cascade().empty()

    def test_unavailable_is_a_runtime_error(self):
        assert issubclass(fd.FaceDetectorUnavailableError, RuntimeError)


class TestDetectFacesWithStandIn:
    def test_sorts_largest_first(self, monkeypatch, cascade_dir):
        _fake_cv2(monkeypatch, data_dir=cascade_dir)
        faces = fd.detect_faces(np.full((64, 64, 3), 9, dtype=np.uint8))
        assert [(f.w, f.h) for f in faces] == [(30, 40), (10, 10)]

    def test_caps_at_max_faces(self, monkeypatch, cascade_dir):
        _fake_cv2(monkeypatch, data_dir=cascade_dir)
        faces = fd.detect_faces(
            np.full((64, 64, 4), 9, dtype=np.uint8), fd.DetectorOptions(max_faces=1),
        )
        assert len(faces) == 1

    def test_no_detections_returns_empty_list(self, monkeypatch, cascade_dir):
        _fake_cv2(monkeypatch, data_dir=cascade_dir)
        assert fd.detect_faces(np.zeros((8, 8, 3), dtype=np.uint8)) == []

    def test_unavailable_propagates(self, monkeypatch):
        _fake_cv2(monkeypatch, classifier=None)
        with pytest.raises(fd.FaceDetectorUnavailableError):
            fd.detect_faces(np.zeros((8, 8, 3), dtype=np.uint8))


class TestFaceTag:
    def test_round_trip(self):
        t = fd.FaceTag(x=10, y=20, w=50, h=60, name="Alice")
        assert fd.FaceTag.from_dict(t.to_dict()) == t

    def test_from_dict_default_name_empty(self):
        t = fd.FaceTag.from_dict({"x": 1, "y": 2, "w": 3, "h": 4})
        assert t.name == ""


class TestDetectFacesValidation:
    def test_rejects_2d_array(self):
        with pytest.raises(ValueError):
            fd.detect_faces(np.zeros((16, 16), dtype=np.uint8))

    def test_rejects_single_channel(self):
        with pytest.raises(ValueError):
            fd.detect_faces(np.zeros((16, 16, 2), dtype=np.uint8))


@requires_haar
class TestDetectFacesOutput:
    def test_noise_image_returns_empty_list(self):
        rng = np.random.default_rng(0)
        arr = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
        faces = fd.detect_faces(arr)
        assert isinstance(faces, list)
        # Random noise shouldn't produce any detections.
        assert faces == [] or all(isinstance(f, fd.FaceTag) for f in faces)

    def test_blank_image_returns_empty_list(self):
        arr = np.full((64, 64, 3), 200, dtype=np.uint8)
        faces = fd.detect_faces(arr)
        assert faces == []


class TestTagDictRoundtrip:
    def test_skips_non_dict_items(self):
        raw = [
            {"x": 1, "y": 2, "w": 3, "h": 4, "name": "Bob"},
            "junk",
            {"missing": "fields"},
        ]
        tags = fd.face_tags_from_dict_list(raw)
        assert len(tags) == 1

    def test_to_dict_list_round_trip(self):
        tags = [fd.FaceTag(1, 2, 3, 4, "A"), fd.FaceTag(5, 6, 7, 8, "B")]
        out = fd.face_tags_to_dict_list(tags)
        back = fd.face_tags_from_dict_list(out)
        assert back == tags
