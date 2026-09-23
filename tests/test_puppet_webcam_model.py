"""The face-landmark model is only used once its SHA-256 checks out.

``_face_landmarker_model_path`` downloads MediaPipe's ``face_landmarker.task``
on first use. Driven with the network and ``app_dir`` patched, so no GL widget
or download is involved and the file runs on CI.
"""
from __future__ import annotations

import hashlib

import pytest

from Imervue.puppet import webcam_tracker as wt

_GOOD = b"the genuine model bytes"


class _Resp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


@pytest.fixture
def model_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("Imervue.system.app_paths.app_dir", lambda: tmp_path)
    monkeypatch.setattr(wt, "_FACE_LANDMARKER_SHA256", hashlib.sha256(_GOOD).hexdigest())
    return tmp_path / "models"


def _serve(monkeypatch, data: bytes) -> list:
    calls: list = []

    def fake(url):
        calls.append(url)
        return _Resp(data)

    monkeypatch.setattr(wt, "_https_urlopen", fake)
    return calls


def _refuse_network(monkeypatch):
    def fake(_url):
        raise AssertionError("should not have called the network")

    monkeypatch.setattr(wt, "_https_urlopen", fake)


def test_pinned_hash_is_a_sha256():
    assert len(wt._FACE_LANDMARKER_SHA256) == 64
    int(wt._FACE_LANDMARKER_SHA256, 16)


def test_verified_cached_model_is_reused_without_the_network(model_dir, monkeypatch):
    model_dir.mkdir()
    (model_dir / "face_landmarker.task").write_bytes(_GOOD)
    _refuse_network(monkeypatch)
    assert wt._face_landmarker_model_path() == model_dir / "face_landmarker.task"


def test_first_use_downloads_and_saves_the_verified_model(model_dir, monkeypatch):
    calls = _serve(monkeypatch, _GOOD)
    out = wt._face_landmarker_model_path()
    assert calls == [wt._FACE_LANDMARKER_MODEL_URL]
    assert out.read_bytes() == _GOOD
    assert not (model_dir / "face_landmarker.task.part").exists()


def test_tampered_cache_is_replaced_by_a_verified_download(model_dir, monkeypatch, caplog):
    model_dir.mkdir()
    (model_dir / "face_landmarker.task").write_bytes(b"tampered")
    calls = _serve(monkeypatch, _GOOD)
    with caplog.at_level("DEBUG", logger="Imervue"):
        out = wt._face_landmarker_model_path()
    assert len(calls) == 1
    assert out.read_bytes() == _GOOD
    assert any("checksum" in r.getMessage() for r in caplog.records)


def test_download_with_the_wrong_hash_is_refused_and_not_saved(model_dir, monkeypatch):
    _serve(monkeypatch, b"something else")
    with pytest.raises(wt._WebcamSetupError, match="checksum"):
        wt._face_landmarker_model_path()
    assert not (model_dir / "face_landmarker.task").exists()


def test_network_failure_is_a_setup_error(model_dir, monkeypatch):
    def boom(_url):
        raise OSError("simulated network failure")

    monkeypatch.setattr(wt, "_https_urlopen", boom)
    with pytest.raises(wt._WebcamSetupError, match="download"):
        wt._face_landmarker_model_path()
