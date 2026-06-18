"""Object removal — flood-fill mask selection + diffusion inpainting.

Click a point, grow a colour-similar connected region into a mask, then fill it
with the model-free diffusion inpainter (:func:`Imervue.image.inpaint.inpaint_diffusion`).
A generative ONNX path (e.g. LaMa) can layer on later; shipping object removal
as a plugin already isolates that heavier dependency from the main viewer.

All functions here are pure NumPy — no Qt — so they are fully unit-testable.
"""
from __future__ import annotations

import numpy as np

from Imervue.image.inpaint import DEFAULT_ITERATIONS, inpaint_diffusion

TOLERANCE_MIN = 0
TOLERANCE_MAX = 255
GROW_MAX = 20
_RGB_CHANNELS = 3
_NEIGHBOURS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _is_fillable(candidate: np.ndarray, mask: np.ndarray,
                 h: int, w: int, y: int, x: int) -> bool:
    return 0 <= y < h and 0 <= x < w and candidate[y, x] and not mask[y, x]


def flood_fill_mask(arr: np.ndarray, seed_x: int, seed_y: int,
                    tolerance: int) -> np.ndarray:
    """Boolean ``HxW`` mask of the colour-similar region connected to the seed.

    A pixel joins the region when every RGB channel is within *tolerance* of the
    seed colour and it is 4-connected to the seed. The seed itself is always
    included (it matches itself), so the mask is never empty for an in-bounds
    seed.
    """
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] < _RGB_CHANNELS:
        raise ValueError(f"expected HxWxC (C>=3) image, got {arr.shape}")
    rgb = arr[..., :_RGB_CHANNELS].astype(np.int16)
    h, w = rgb.shape[:2]
    sx = max(0, min(int(seed_x), w - 1))
    sy = max(0, min(int(seed_y), h - 1))
    tol = max(TOLERANCE_MIN, int(tolerance))
    candidate = np.abs(rgb - rgb[sy, sx]).max(axis=2) <= tol
    mask = np.zeros((h, w), dtype=bool)
    mask[sy, sx] = True
    stack = [(sy, sx)]
    while stack:
        y, x = stack.pop()
        for dy, dx in _NEIGHBOURS:
            ny, nx = y + dy, x + dx
            if _is_fillable(candidate, mask, h, w, ny, nx):
                mask[ny, nx] = True
                stack.append((ny, nx))
    return mask


def grow_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    """Dilate *mask* by *radius* pixels (4-connected) to cover soft edges."""
    grown = np.asarray(mask, dtype=bool)
    for _ in range(max(0, int(radius))):
        up = np.zeros_like(grown)
        up[:-1] = grown[1:]
        down = np.zeros_like(grown)
        down[1:] = grown[:-1]
        left = np.zeros_like(grown)
        left[:, :-1] = grown[:, 1:]
        right = np.zeros_like(grown)
        right[:, 1:] = grown[:, :-1]
        grown = grown | up | down | left | right
    return grown


def build_mask(arr: np.ndarray, seed_x: int, seed_y: int,
               tolerance: int, grow: int = 0) -> np.ndarray:
    """Flood-fill a mask at the seed, then grow it by *grow* pixels."""
    mask = flood_fill_mask(arr, seed_x, seed_y, tolerance)
    return grow_mask(mask, grow) if grow > 0 else mask


def remove_object(arr: np.ndarray, mask: np.ndarray,
                  iterations: int = DEFAULT_ITERATIONS) -> np.ndarray:
    """Fill the masked region of *arr* by diffusion inpainting."""
    return inpaint_diffusion(arr, mask, iterations=iterations)


# ---------------------------------------------------------------------------
# Optional generative (ONNX) inpainting — pure pre/post helpers + runner
# ---------------------------------------------------------------------------

_NCHW_RANK = 4
_CHANNEL_AXIS = 1


def _channel_dim(shape) -> int | None:
    """Return the channel count of an NCHW input shape, or None if unknown."""
    if len(shape) != _NCHW_RANK:
        return None
    channels = shape[_CHANNEL_AXIS]
    return channels if isinstance(channels, int) else None


def classify_onnx_inputs(specs: list[tuple[str, list]]) -> tuple[str | None, str | None]:
    """Pick the image and (optional) mask input names from ONNX input specs.

    *specs* is ``[(name, shape), …]``. The 3-channel input is the image and the
    1-channel input is the mask; when no 3-channel input is found the first
    input is assumed to be the image (image-only inpaint models).
    """
    image_name = mask_name = None
    for name, shape in specs:
        channels = _channel_dim(shape)
        if channels == _RGB_CHANNELS and image_name is None:
            image_name = name
        elif channels == 1 and mask_name is None:
            mask_name = name
    if image_name is None and specs:
        image_name = specs[0][0]
    return image_name, mask_name


def to_nchw(rgb: np.ndarray) -> np.ndarray:
    """``HxWx3`` float → ``1x3xHxW`` float32 (NCHW) for an ONNX image input."""
    return np.transpose(rgb, (2, 0, 1))[None, ...].astype(np.float32)


def mask_to_nchw(mask: np.ndarray) -> np.ndarray:
    """``HxW`` bool → ``1x1xHxW`` float32 mask for an ONNX mask input."""
    return np.asarray(mask, dtype=bool).astype(np.float32)[None, None, ...]


def composite_inpaint(original: np.ndarray, model_rgb: np.ndarray,
                      mask: np.ndarray) -> np.ndarray:
    """Replace only the masked pixels of *original* with the model's output."""
    out = original.copy()
    out[mask, :_RGB_CHANNELS] = model_rgb[mask]
    return out


def onnx_inpaint(arr: np.ndarray, mask: np.ndarray, model_path: str) -> np.ndarray:
    """Run a generative ONNX inpaint model over the masked region.

    The model is expected to keep the input resolution and accept a 3-channel
    image (and optionally a 1-channel mask) in NCHW float [0, 1]. ``onnxruntime``
    is optional — its absence surfaces as ``ImportError`` so the dialog can fall
    back to diffusion.
    """
    if arr.ndim != _RGB_CHANNELS or arr.shape[2] < _RGB_CHANNELS:
        raise ValueError(f"expected HxWxC (C>=3) image, got {arr.shape}")
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError(
            "onnxruntime is required for the generative inpaint path.",
        ) from exc
    session = ort.InferenceSession(
        str(model_path), providers=ort.get_available_providers(),
    )
    mask_bool = np.asarray(mask, dtype=bool)
    rgb = arr[..., :_RGB_CHANNELS].astype(np.float32) / 255.0
    image_name, mask_name = classify_onnx_inputs(
        [(i.name, i.shape) for i in session.get_inputs()],
    )
    if mask_name is None:
        rgb = rgb.copy()
        rgb[mask_bool] = 0.0
    feed = {image_name: to_nchw(rgb)}
    if mask_name is not None:
        feed[mask_name] = mask_to_nchw(mask_bool)
    output = session.run(None, feed)[0]
    model_rgb = np.clip(
        np.transpose(output[0], (1, 2, 0)) * 255.0, 0, 255,
    ).astype(np.uint8)
    if model_rgb.shape[:2] != arr.shape[:2]:
        raise ValueError("ONNX inpaint model changed the image resolution")
    return composite_inpaint(arr, model_rgb, mask_bool)


def image_coord_from_click(wx: float, wy: float, label_w: int, label_h: int,
                           img_w: int, img_h: int) -> tuple[int, int] | None:
    """Map a click on a fit-scaled, centred preview to image pixel coords.

    Returns ``None`` when the click falls in the letterbox margin outside the
    drawn image.
    """
    if img_w <= 0 or img_h <= 0 or label_w <= 0 or label_h <= 0:
        return None
    scale = min(label_w / img_w, label_h / img_h)
    disp_w, disp_h = img_w * scale, img_h * scale
    off_x, off_y = (label_w - disp_w) / 2, (label_h - disp_h) / 2
    ix, iy = (wx - off_x) / scale, (wy - off_y) / scale
    if not (0 <= ix < img_w and 0 <= iy < img_h):
        return None
    return int(ix), int(iy)
