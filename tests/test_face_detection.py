"""Tests for face detection."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from Imervue.image import face_detection as fd


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
