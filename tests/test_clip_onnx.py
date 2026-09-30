"""Tests for the ONNX CLIP backend, with a stand-in onnxruntime and Hub.

No model is downloaded: ``model_file`` is pointed at a tiny vocabulary and
``onnxruntime`` at a fake module whose sessions return fixed embeddings.
"""
from __future__ import annotations

import json
import sys
import types

import numpy as np
import pytest
from PIL import Image

from Imervue.library import clip_onnx
from Imervue.library.clip_onnx import (
    CLIP_VIT_B32,
    IMAGE_SIZE,
    MEAN,
    STD,
    ClipModel,
    OnnxClipEmbedder,
    normalise_rows,
    preferred_providers,
    preprocess,
    rank_labels,
)

_CUDA, _CPU, _DML = "CUDAExecutionProvider", "CPUExecutionProvider", "DmlExecutionProvider"


# --- preprocessing -----------------------------------------------------------

def test_preprocess_is_a_normalised_224_batch():
    batch = preprocess(Image.new("RGB", (640, 480), (255, 128, 0)))
    assert batch.shape == (1, 3, IMAGE_SIZE, IMAGE_SIZE)
    assert batch.dtype == np.float32
    expected = (np.array([255, 128, 0], dtype=np.float32) / 255.0 - MEAN) / STD
    assert np.allclose(batch[0, :, 100, 100], expected, atol=1e-5)


def test_preprocess_crops_the_centre_of_a_wide_picture():
    arr = np.zeros((224, 672, 3), dtype=np.uint8)
    arr[:, 224:448] = 255                          # only the middle third is white
    batch = preprocess(Image.fromarray(arr))
    white = (1.0 - MEAN) / STD
    assert np.allclose(batch[0, :, :, 5], white[:, None], atol=1e-4)
    assert np.allclose(batch[0, :, :, -5], white[:, None], atol=1e-4)


@pytest.mark.parametrize("size", [(10, 5), (224, 900), (333, 224), (1, 1)])
def test_preprocess_any_size_gives_224_square(size):
    assert preprocess(Image.new("RGB", size)).shape == (1, 3, IMAGE_SIZE, IMAGE_SIZE)


def test_preprocess_drops_alpha_and_greyscale_modes():
    assert preprocess(Image.new("RGBA", (300, 300))).shape[1] == 3
    assert preprocess(Image.new("L", (300, 300))).shape[1] == 3


# --- pure helpers ------------------------------------------------------------

@pytest.mark.parametrize(("available", "expected"), [
    ([_CUDA, _CPU], [_CUDA, _CPU]),
    (["TensorrtExecutionProvider", _CUDA, _CPU], [_CUDA, _CPU]),
    ([_DML, _CPU], [_CPU]),                        # DirectML may be the integrated GPU
    ([_CPU], [_CPU]),
    ([], [_CPU]),
])
def test_preferred_providers_never_pick_directml(available, expected):
    assert preferred_providers(available) == expected


def test_normalise_rows_unit_length_and_zero_row_kept():
    rows = normalise_rows(np.array([[3.0, 4.0], [0.0, 0.0]]))
    assert np.allclose(rows, [[0.6, 0.8], [0.0, 0.0]])


def test_rank_labels_best_first_above_the_floor():
    labels = ["cat", "dog", "car"]
    vectors = np.eye(3, dtype=np.float32)
    image = np.array([0.9, 0.3, 0.0], dtype=np.float32)
    assert rank_labels(image, vectors, labels) == ["cat"]      # softmax at 100x is sharp
    close = np.array([1.0, 0.99, 0.0], dtype=np.float32)
    assert rank_labels(close, vectors, labels) == ["cat", "dog"]
    assert rank_labels(close, vectors, labels, top=1) == ["cat"]
    assert rank_labels(close, vectors, labels, top=0) == []
    assert rank_labels(close, vectors, labels, min_probability=0.99) == []


def test_rank_labels_without_labels():
    assert rank_labels(np.ones(3, np.float32), np.zeros((0, 3), np.float32), []) == []


def test_model_id_names_repo_commit_and_variant():
    assert CLIP_VIT_B32.model_id == (
        "Xenova/clip-vit-base-patch32@d15189d7028b:vision_model_quantized")
    assert CLIP_VIT_B32.files() == (
        "onnx/vision_model_quantized.onnx", "onnx/text_model_quantized.onnx",
        "vocab.json", "merges.txt")
    assert len(CLIP_VIT_B32.revision) == 40            # a pinned commit, not a branch


# --- model files -------------------------------------------------------------

def test_model_file_downloads_the_pinned_revision(monkeypatch):
    import huggingface_hub
    calls = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        return "/cache/" + kwargs["filename"]

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_download)
    assert clip_onnx.model_file(CLIP_VIT_B32, "vocab.json", download=True) == "/cache/vocab.json"
    assert calls == [{"repo_id": CLIP_VIT_B32.repo, "filename": "vocab.json",
                      "revision": CLIP_VIT_B32.revision, "local_files_only": False}]


def test_model_file_not_cached_is_an_oserror(monkeypatch):
    import huggingface_hub
    from huggingface_hub.errors import LocalEntryNotFoundError

    def missing(**_kwargs):
        raise LocalEntryNotFoundError("not cached")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", missing)
    with pytest.raises(OSError, match="unavailable"):
        clip_onnx.model_file(CLIP_VIT_B32, "vocab.json", download=False)
    assert clip_onnx.model_downloaded() is False


def test_model_downloaded_when_every_file_is_cached(monkeypatch):
    monkeypatch.setattr(clip_onnx, "model_file", lambda _m, name, *, download: f"/c/{name}")
    monkeypatch.setattr(clip_onnx, "backend_importable", lambda: True)
    assert clip_onnx.model_downloaded() is True
    assert OnnxClipEmbedder().is_downloaded() is True


def test_nothing_is_downloaded_without_onnxruntime(monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    assert clip_onnx.backend_importable() is False
    assert clip_onnx.model_downloaded() is False


# --- the embedder, on a fake onnxruntime --------------------------------------

class _FakeSession:
    created: list = []

    def __init__(self, path, providers):
        self.path = path
        # CUDA was listed but "fails to load": the session runs on the CPU only.
        self._providers = [p for p in providers if p != _CUDA] or [_CPU]
        self.inputs: list = []
        _FakeSession.created.append((path, list(providers)))

    def get_providers(self):
        return self._providers

    def run(self, outputs, feeds):
        self.inputs.append(feeds)
        if outputs == ["text_embeds"]:
            ids = feeds["input_ids"]
            return [np.array([[float(ids.shape[1]), 0.0, 0.0, 1.0]], dtype=np.float32)]
        return [np.array([[0.0, 2.0, 0.0, 0.0]], dtype=np.float32)]


@pytest.fixture
def fake_backend(tmp_path, monkeypatch):
    vocab = {"a</w>": 320, "cat</w>": 2368, "<|startoftext|>": 49406, "<|endoftext|>": 49407}
    (tmp_path / "vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
    (tmp_path / "merges.txt").write_text("#version: 0.2\nc a\nca t</w>\n", encoding="utf-8")
    files = {"vocab.json": tmp_path / "vocab.json", "merges.txt": tmp_path / "merges.txt"}
    requested = []

    def fake_file(_model, name, *, download):
        requested.append((name, download))
        return str(files.get(name, tmp_path / name))

    fake_ort = types.SimpleNamespace(
        get_available_providers=lambda: [_CUDA, _CPU], InferenceSession=_FakeSession)
    _FakeSession.created = []
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setattr(clip_onnx, "model_file", fake_file)
    return requested


def test_prepare_opens_both_sessions_once(fake_backend):
    embedder = OnnxClipEmbedder()
    embedder.prepare()
    embedder.prepare()
    paths = [path.replace("\\", "/") for path, _ in _FakeSession.created]
    assert len(paths) == 2
    assert paths[0].endswith("text_model_quantized.onnx")
    assert paths[1].endswith("vision_model_quantized.onnx")
    assert all(download for _name, download in fake_backend)


def test_the_vision_session_skips_a_provider_the_text_session_could_not_load(fake_backend):
    OnnxClipEmbedder().prepare()
    (_, text_providers), (_, vision_providers) = _FakeSession.created
    assert text_providers == [_CUDA, _CPU]
    assert vision_providers == [_CPU]


def test_an_embedder_without_download_rights_asks_for_cached_files_only(fake_backend):
    OnnxClipEmbedder(allow_download=False).prepare()
    assert {download for _name, download in fake_backend} == {False}


def test_embed_texts_tokenises_and_normalises(fake_backend):
    embedder = OnnxClipEmbedder()
    vectors = embedder.embed_texts(["a cat", "cat"])
    assert vectors.shape == (2, 4)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    text_session = embedder._text  # noqa: SLF001
    assert text_session.inputs[0]["input_ids"].tolist() == [[49406, 320, 2368, 49407]]
    assert text_session.inputs[0]["input_ids"].dtype == np.int64
    assert np.allclose(embedder.embed_text("cat"), vectors[1])


def test_embed_image_reads_the_picture_as_shown(fake_backend, tmp_path):
    path = tmp_path / "p.png"
    Image.new("RGB", (300, 200), (10, 20, 30)).save(path)
    embedder = OnnxClipEmbedder()
    vector = embedder.embed_image(path)
    assert np.allclose(vector, [0.0, 1.0, 0.0, 0.0])
    feeds = embedder._vision.inputs[0]  # noqa: SLF001
    assert feeds["pixel_values"].shape == (1, 3, IMAGE_SIZE, IMAGE_SIZE)


def test_embed_image_of_an_unreadable_file_is_none(fake_backend, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert OnnxClipEmbedder().embed_image(bad) is None


def test_prepare_passes_on_a_missing_model(monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", types.SimpleNamespace(
        get_available_providers=lambda: [_CPU], InferenceSession=_FakeSession))

    def offline(_model, name, *, download):
        raise OSError(f"CLIP model file {name} is unavailable: offline")

    monkeypatch.setattr(clip_onnx, "model_file", offline)
    with pytest.raises(OSError, match="offline"):
        OnnxClipEmbedder().prepare()


def test_default_embedder_is_shared(monkeypatch):
    monkeypatch.setattr(clip_onnx, "_default_embedder", None)
    first = clip_onnx.default_embedder()
    assert clip_onnx.default_embedder() is first
    assert first.model_id == CLIP_VIT_B32.model_id


def test_a_custom_model_keeps_its_own_id():
    model = ClipModel(repo="me/clip", revision="a" * 40, vision="v.onnx", text="t.onnx")
    assert OnnxClipEmbedder(model).model_id == "me/clip@aaaaaaaaaaaa:v"
