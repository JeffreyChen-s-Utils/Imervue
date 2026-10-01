"""CLIP ViT-B/32 on onnxruntime: image and text embeddings without torch.

The model is OpenAI's CLIP ViT-B/32 as ONNX (int8-quantised text and vision
encoders, about 150 MB together), downloaded once from Hugging Face at a pinned
commit and then read from the local cache. Text is tokenised by
:mod:`Imervue.library.clip_tokenizer`; images are prepared the way CLIP was
trained (shortest edge to 224 px bicubic, centre crop, OpenAI mean / std).

Inference runs on CUDA when ``onnxruntime`` has it (an NVIDIA card, never an
integrated GPU), otherwise on the CPU. DirectML is not used: its default device
is often the integrated GPU of a hybrid laptop.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.library.clip_tokenizer import ClipTokenizer

logger = logging.getLogger("Imervue.library.clip_onnx")

#: pip packages the backend needs, as ``(import name, pip name)`` for ``ensure_dependencies``.
REQUIRED_PACKAGES = [
    ("onnxruntime", "onnxruntime"),
    ("huggingface_hub", "huggingface_hub"),
]
IMAGE_SIZE = 224
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
EMBED_DIM = 512
_CUDA = "CUDAExecutionProvider"
_CPU = "CPUExecutionProvider"


@dataclass(frozen=True)
class ClipModel:
    """Where one CLIP export lives: repository, pinned commit and file names."""

    repo: str
    revision: str
    vision: str
    text: str
    vocab: str = "vocab.json"
    merges: str = "merges.txt"

    @property
    def model_id(self) -> str:
        """Names the embedding space; embeddings from another model id are not comparable."""
        return f"{self.repo}@{self.revision[:12]}:{Path(self.vision).stem}"

    def files(self) -> tuple[str, ...]:
        """Every file the backend reads."""
        return (self.vision, self.text, self.vocab, self.merges)


CLIP_VIT_B32 = ClipModel(
    repo="Xenova/clip-vit-base-patch32",
    revision="d15189d7028b43f1d3e65039190477f6af591c2a",
    vision="onnx/vision_model_quantized.onnx",
    text="onnx/text_model_quantized.onnx",
)


def backend_importable() -> bool:
    """Whether onnxruntime and huggingface_hub can be imported."""
    try:
        import huggingface_hub  # noqa: F401 - availability probe
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def model_file(model: ClipModel, name: str, *, download: bool) -> str:
    """Local path of one of *model*'s files; with ``download`` fetch it at the pinned revision.

    Raises ``OSError`` when it is not in the cache and may not or cannot be
    fetched (offline, or the Hub refuses).
    """
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import HfHubHTTPError, LocalEntryNotFoundError
    try:
        return hf_hub_download(repo_id=model.repo, filename=name, revision=model.revision,
                               local_files_only=not download)
    except (LocalEntryNotFoundError, HfHubHTTPError, ValueError) as exc:
        raise OSError(f"CLIP model file {name} is unavailable: {exc}") from exc


def model_downloaded(model: ClipModel = CLIP_VIT_B32) -> bool:
    """Whether every file of *model* is already in the local cache (never downloads)."""
    if not backend_importable():
        return False
    try:
        for name in model.files():
            model_file(model, name, download=False)
    except OSError:
        return False
    return True


def preferred_providers(available: Sequence[str]) -> list[str]:
    """CUDA first when onnxruntime offers it, then the CPU; DirectML is left out."""
    return [_CUDA, _CPU] if _CUDA in available else [_CPU]


def preprocess(image: Image.Image) -> np.ndarray:
    """A ``1x3x224x224`` float32 batch: shortest edge to 224 (bicubic), centre crop, normalised."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    scale = IMAGE_SIZE / min(width, height)
    size = (max(IMAGE_SIZE, int(width * scale)), max(IMAGE_SIZE, int(height * scale)))
    resized = rgb.resize(size, Image.Resampling.BICUBIC)
    left = (size[0] - IMAGE_SIZE) // 2
    top = (size[1] - IMAGE_SIZE) // 2
    crop = resized.crop((left, top, left + IMAGE_SIZE, top + IMAGE_SIZE))
    pixels = (np.asarray(crop, dtype=np.float32) / 255.0 - MEAN) / STD
    return pixels.transpose(2, 0, 1)[np.newaxis].astype(np.float32)


def normalise_rows(vectors: np.ndarray) -> np.ndarray:
    """Each row scaled to unit length; an all-zero row stays zero."""
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return np.where(norms > 0, vectors / np.maximum(norms, 1e-12), vectors)


class OnnxClipEmbedder:
    """Text and image embeddings from the ONNX CLIP model, loaded on first use.

    :meth:`prepare` downloads the model if needed and opens the two sessions;
    the ``embed_*`` methods call it themselves. Safe to share between threads.
    """

    def __init__(self, model: ClipModel = CLIP_VIT_B32, *, allow_download: bool = True) -> None:
        self.model = model
        self.dim = EMBED_DIM
        self._allow_download = allow_download
        self._lock = threading.Lock()
        self._vision = None
        self._text = None
        self._tokenizer: ClipTokenizer | None = None

    @property
    def model_id(self) -> str:
        """The embedding space these vectors live in (see :attr:`ClipModel.model_id`)."""
        return self.model.model_id

    def is_downloaded(self) -> bool:
        """Whether every model file is already in the local cache."""
        return model_downloaded(self.model)

    def prepare(self) -> None:
        """Fetch the model (once) and open its sessions; ``OSError`` when it can't be had."""
        with self._lock:
            if self._vision is not None:
                return
            import onnxruntime as ort
            paths = {name: model_file(self.model, name, download=self._allow_download)
                     for name in self.model.files()}
            providers = preferred_providers(ort.get_available_providers())
            self._tokenizer = ClipTokenizer.from_files(paths[self.model.vocab],
                                                       paths[self.model.merges])
            self._text = ort.InferenceSession(paths[self.model.text], providers=providers)
            # CUDA listed but its libraries missing: the text session fell back to the
            # CPU already, so the vision session doesn't try (and log the failure) again.
            providers = self._text.get_providers()
            self._vision = ort.InferenceSession(paths[self.model.vision], providers=providers)
            logger.info("CLIP model %s on %s", self.model_id, self._vision.get_providers()[0])

    def embed_text(self, text: str) -> np.ndarray:
        """The unit-length embedding of *text*."""
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        """One unit-length row per text."""
        self.prepare()
        rows = []
        for text in texts:   # the export takes one unpadded sequence at a time
            ids = np.array([self._tokenizer.encode(text)], dtype=np.int64)
            rows.append(self._text.run(["text_embeds"], {"input_ids": ids})[0][0])
        return normalise_rows(np.stack(rows))

    def embed_image(self, path: str | Path) -> np.ndarray | None:
        """The unit-length embedding of the picture as shown; ``None`` if it can't be read."""
        self.prepare()
        from Imervue.image.formats import ensure_pillow_opener
        from Imervue.image.shown import as_shown_8bit
        try:
            ensure_pillow_opener(Path(path).suffix)
            with Image.open(path) as im:
                # A sideways photo embeds as a different picture; turn it as it is shown.
                batch = preprocess(as_shown_8bit(im, mode="RGB"))
        except IMAGE_READ_ERRORS as exc:
            logger.debug("CLIP image decode failed for %s: %s", path, exc)
            return None
        vector = self._vision.run(["image_embeds"], {"pixel_values": batch})[0][0]
        return normalise_rows(vector[np.newaxis])[0]


def rank_labels(image_vector: np.ndarray, label_vectors: np.ndarray, labels: Sequence[str],
                *, top: int = 3, min_probability: float = 0.15) -> list[str]:
    """Zero-shot labels: softmax over ``100 x`` cosine similarity, best first.

    Keeps at most *top* labels whose probability reaches *min_probability*.
    """
    if len(labels) == 0:
        return []
    logits = 100.0 * (normalise_rows(label_vectors) @ normalise_rows(image_vector[np.newaxis])[0])
    probabilities = np.exp(logits - logits.max())
    probabilities /= probabilities.sum()
    order = np.argsort(-probabilities)[:max(0, top)]
    return [labels[int(i)] for i in order if probabilities[int(i)] >= min_probability]


_default_embedder: OnnxClipEmbedder | None = None
_default_lock = threading.Lock()


def default_embedder() -> OnnxClipEmbedder:
    """The shared embedder, so semantic search and auto-tag load the model once."""
    global _default_embedder
    with _default_lock:
        if _default_embedder is None:
            _default_embedder = OnnxClipEmbedder()
        return _default_embedder
