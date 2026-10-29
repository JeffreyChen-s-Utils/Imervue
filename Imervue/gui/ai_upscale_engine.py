"""
AI 圖片放大的方法登錄與推論 (Qt-free)
Upscale method registry and ONNX inference helpers for the AI upscale dialog.

The Real-ESRGAN model registry (each entry pinned to a Hugging Face commit),
the traditional resampling methods, the folder scan, the model download and the
tiled ONNX inference. Nothing here imports Qt; ``fill_upscale_model_combo`` only
calls ``addItem`` on the combo it is handed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.system.image_listing import list_images
from Imervue.image.formats import JPEG_EXTENSIONS

if TYPE_CHECKING:
    from PySide6.QtWidgets import QComboBox

# ---------------------------------------------------------------------------
# Model registry — HuggingFace repo + filename for each variant
# ---------------------------------------------------------------------------
# Each model is pinned to a Hugging Face commit (bandit B615): a later push to
# the repository cannot change the weights that get downloaded and run.
_OWL_REVISION = "d783e61585b3d83a85c91ca8a3b299e8ade94d72"

UPSCALE_MODELS = {
    "realesrgan-x4plus": {
        "repo": "OwlMaster/AllFilesRope",
        "file": "RealESRGAN_x4plus.fp16.onnx",
        "revision": _OWL_REVISION,
        "scale": 4,
        "desc_key": "upscale_model_x4",
        "desc_default": "Real-ESRGAN x4 (general, best quality)",
    },
    "realesrgan-x4plus-anime": {
        "repo": "xiongjie/lightweight-real-ESRGAN-anime",
        "file": "RealESRGAN_x4plus_anime_4B32F.onnx",
        "revision": "695895c3a4ab540e3710b5e4a3d6f7e734bc1668",
        "scale": 4,
        "desc_key": "upscale_model_x4_anime",
        "desc_default": "Real-ESRGAN x4 Anime (optimized for illustrations)",
    },
    "realesrgan-x2plus": {
        "repo": "OwlMaster/AllFilesRope",
        "file": "RealESRGAN_x2plus.fp16.onnx",
        "revision": _OWL_REVISION,
        "scale": 2,
        "desc_key": "upscale_model_x2",
        "desc_default": "Real-ESRGAN x2 (general, 2x upscale)",
    },
}

_TRAD_PREFIX = "trad:"

# Traditional (non-AI) resampling methods — no dependencies, lossless.
# Keys use _TRAD_PREFIX to distinguish from AI model keys.
TRADITIONAL_METHODS = {
    f"{_TRAD_PREFIX}lanczos": {
        "desc_key": "upscale_method_lanczos",
        "desc_default": "Lanczos (high quality, lossless)",
    },
    f"{_TRAD_PREFIX}bicubic": {
        "desc_key": "upscale_method_bicubic",
        "desc_default": "Bicubic (fast, good quality)",
    },
    f"{_TRAD_PREFIX}nearest": {
        "desc_key": "upscale_method_nearest",
        "desc_default": "Nearest Neighbor (pixel art)",
    },
}

# Map traditional key → PIL Resampling enum (resolved at runtime to avoid
# importing PIL at module level).
_TRAD_RESAMPLING = {
    f"{_TRAD_PREFIX}lanczos": "LANCZOS",
    f"{_TRAD_PREFIX}bicubic": "BICUBIC",
    f"{_TRAD_PREFIX}nearest": "NEAREST",
}

REQUIRED_PACKAGES = [
    ("onnxruntime", "onnxruntime"),
    ("huggingface_hub", "huggingface_hub"),
]


def fill_upscale_model_combo(combo: QComboBox, lang: dict) -> None:
    """Add every upscale method to ``combo``: traditional (dependency-free) first, then AI.

    Item text comes from ``lang`` with each method's default description as the
    fallback; item data is the method key.
    """
    for methods in (TRADITIONAL_METHODS, UPSCALE_MODELS):
        for key, info in methods.items():
            combo.addItem(lang.get(info["desc_key"], info["desc_default"]), key)


_IMAGE_EXTS = frozenset({
    ".png", ".bmp", ".tiff", ".tif", ".webp",
}) | JPEG_EXTENSIONS


def _scan_folder(folder: str, recursive: bool = False) -> list[str]:
    """Collect image paths from *folder*, in natural name order."""
    return list_images(folder, _IMAGE_EXTS, recursive=recursive)

# Tile size for tiled inference (prevents OOM on large images)
_TILE_SIZE = 512
_TILE_PAD = 10


# ---------------------------------------------------------------------------
# ONNX inference helpers
# ---------------------------------------------------------------------------

def _download_model(model_key: str) -> str:
    """Download model from HF and return local path.

    Every entry in :data:`UPSCALE_MODELS` pins a commit ``revision``, so a
    future compromise of the HF repo cannot silently swap the weights we load.
    """
    from huggingface_hub import hf_hub_download
    info = UPSCALE_MODELS[model_key]
    return hf_hub_download(
        repo_id=info["repo"],
        filename=info["file"],
        revision=info["revision"],
    )


def _upscale_tile(session, tile_arr):
    """Run ONNX inference on a single tile (HWC uint8 → HWC uint8)."""
    import numpy as np
    # Normalize to float32 [0, 1] and transpose to NCHW
    inp = tile_arr.astype(np.float32) / 255.0
    inp = np.transpose(inp, (2, 0, 1))[np.newaxis, ...]
    result = session.run(None, {session.get_inputs()[0].name: inp})[0]
    # Back to HWC uint8
    out = np.clip(result[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8)
    return out


def _upscale_image(session, img_arr, scale: int, progress_cb=None):
    """Tiled upscale for an entire image (HWC uint8 → HWC uint8).
    Tiles prevent GPU/CPU OOM on large images.
    """
    import numpy as np
    h, w, c = img_arr.shape
    tile = _TILE_SIZE
    pad = _TILE_PAD

    out_h, out_w = h * scale, w * scale
    output = np.zeros((out_h, out_w, c), dtype=np.uint8)

    tiles_y = (h + tile - 1) // tile
    tiles_x = (w + tile - 1) // tile
    total_tiles = tiles_y * tiles_x
    done = 0

    for yi in range(tiles_y):
        for xi in range(tiles_x):
            # Input tile with padding
            y0 = yi * tile
            x0 = xi * tile
            y1 = min(y0 + tile, h)
            x1 = min(x0 + tile, w)

            # Padded coords (clamped)
            py0 = max(0, y0 - pad)
            px0 = max(0, x0 - pad)
            py1 = min(h, y1 + pad)
            px1 = min(w, x1 + pad)

            tile_in = img_arr[py0:py1, px0:px1, :]
            tile_out = _upscale_tile(session, tile_in)

            # Compute where the non-padded region is in the output tile
            oy0 = (y0 - py0) * scale
            ox0 = (x0 - px0) * scale
            oh = (y1 - y0) * scale
            ow = (x1 - x0) * scale
            oy1 = oy0 + oh
            ox1 = ox0 + ow

            # Place in output
            out_y0 = y0 * scale
            out_x0 = x0 * scale
            output[out_y0:out_y0 + oh, out_x0:out_x0 + ow, :] = \
                tile_out[oy0:oy1, ox0:ox1, :]

            done += 1
            if progress_cb:
                progress_cb(done, total_tiles)

    return output


def _preferred_providers(available: list[str]) -> list[str]:
    """onnxruntime providers to ask for: CUDA and DirectML when present, CPU last."""
    gpu = [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in available]
    return [*gpu, "CPUExecutionProvider"]


def _ai_upscale(session, img, scale: int, progress_cb):
    """Enlarge *img* with the ONNX *session*; an alpha channel is resized alongside."""
    import numpy as np
    from PIL import Image
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    alpha = img.split()[-1] if img.mode == "RGBA" else None
    rgb = img.convert("RGB") if alpha is not None else img
    out_img = Image.fromarray(
        _upscale_image(session, np.array(rgb), scale, progress_cb=progress_cb))
    if alpha is not None:
        out_img.putalpha(alpha.resize(out_img.size, Image.Resampling.LANCZOS))
    return out_img
