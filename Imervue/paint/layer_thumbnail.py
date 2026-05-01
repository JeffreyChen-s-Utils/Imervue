"""Generate small thumbnails of layers for the LayerDock.

Pure-numpy / Qt-free. Produces an HxWx4 RGBA buffer (default 32×32)
from a layer's image, with aspect ratio preserved and the
remainder padded transparent.

A simple content-hash based cache lets the LayerDock re-pull the
same thumbnail on every refresh without re-resampling — the layer's
image only changes when the brush actually paints, so the hash is
stable across the typical refresh storm during a stroke.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_THUMBNAIL_SIZE = 32
MIN_THUMBNAIL_SIZE = 8
MAX_THUMBNAIL_SIZE = 256
CACHE_MAX_ENTRIES = 64


def render_layer_thumbnail(
    image: np.ndarray, *, size: int = DEFAULT_THUMBNAIL_SIZE,
) -> np.ndarray:
    """Return an ``(size, size, 4)`` RGBA thumbnail of ``image``.

    Aspect ratio is preserved by fitting into a centred sub-rect;
    the surrounding pixels stay transparent so the LayerDock can
    paint a chequered "transparency" backdrop behind it without
    fighting an opaque thumbnail border.
    """
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError(
            f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
        )
    if not MIN_THUMBNAIL_SIZE <= int(size) <= MAX_THUMBNAIL_SIZE:
        raise ValueError(
            f"size must be in [{MIN_THUMBNAIL_SIZE}, {MAX_THUMBNAIL_SIZE}], "
            f"got {size!r}",
        )
    target_size = int(size)
    src_h, src_w = image.shape[:2]
    if src_h == 0 or src_w == 0:
        return np.zeros((target_size, target_size, 4), dtype=np.uint8)
    scale = min(target_size / src_w, target_size / src_h)
    out_w = max(1, int(round(src_w * scale)))
    out_h = max(1, int(round(src_h * scale)))
    resized = _resize_rgba(image, (out_h, out_w))
    out = np.zeros((target_size, target_size, 4), dtype=np.uint8)
    x0 = (target_size - out_w) // 2
    y0 = (target_size - out_h) // 2
    out[y0:y0 + out_h, x0:x0 + out_w] = resized
    return out


def render_mask_thumbnail(
    mask: np.ndarray, *, size: int = DEFAULT_THUMBNAIL_SIZE,
) -> np.ndarray:
    """Return an ``(size, size, 4)`` greyscale thumbnail of an HxW mask.

    Mask pixels (0..255) are duplicated into the RGB channels so the
    thumbnail reads as a luminance preview. The output's alpha is
    fully opaque — a layer mask thumbnail is meaningful even when
    the underlying mask values are 0, so we don't want it to vanish
    against the dock background.
    """
    if mask.ndim != 2:
        raise ValueError(
            f"mask must be 2-D, got shape {mask.shape}",
        )
    if mask.dtype != np.uint8:
        raise ValueError(
            f"mask dtype must be uint8, got {mask.dtype}",
        )
    if not MIN_THUMBNAIL_SIZE <= int(size) <= MAX_THUMBNAIL_SIZE:
        raise ValueError(
            f"size must be in [{MIN_THUMBNAIL_SIZE}, {MAX_THUMBNAIL_SIZE}], "
            f"got {size!r}",
        )
    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = mask
    rgba[..., 1] = mask
    rgba[..., 2] = mask
    rgba[..., 3] = 255
    return render_layer_thumbnail(rgba, size=int(size))


# ---------------------------------------------------------------------------
# Lightweight cache
# ---------------------------------------------------------------------------


@dataclass
class ThumbnailCache:
    """LRU-ish cache keyed by ``(id(image), shape, dtype, hash)``.

    The hash is a fast signature based on a small subsample of the
    array — full ``hashlib`` over a 1024² uint8 RGBA buffer would
    cost a million bytes per refresh; the LayerDock fires that
    refresh on every dab. The subsample picks 64 evenly-spaced
    bytes, which is enough collision resistance for the "did the
    user paint anywhere" question we actually need to answer.
    """

    _entries: dict[tuple, np.ndarray]
    _order: list[tuple]
    _max_entries: int = CACHE_MAX_ENTRIES

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES):
        self._entries = {}
        self._order = []
        self._max_entries = int(max_entries)

    def get(
        self,
        image: np.ndarray,
        *,
        size: int = DEFAULT_THUMBNAIL_SIZE,
    ) -> np.ndarray:
        """Return a (cached or freshly-rendered) thumbnail for ``image``."""
        key = _content_signature(image, size=size)
        if key in self._entries:
            # Move-to-end LRU order.
            self._order.remove(key)
            self._order.append(key)
            return self._entries[key]
        thumbnail = render_layer_thumbnail(image, size=size)
        self._entries[key] = thumbnail
        self._order.append(key)
        # Evict the oldest when over capacity.
        while len(self._entries) > self._max_entries:
            oldest = self._order.pop(0)
            self._entries.pop(oldest, None)
        return thumbnail

    def clear(self) -> None:
        self._entries.clear()
        self._order.clear()

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resize_rgba(
    image: np.ndarray, target_shape: tuple[int, int],
) -> np.ndarray:
    """Nearest-neighbour resample of an HxWx4 RGBA buffer."""
    src_h, src_w = image.shape[:2]
    dst_h, dst_w = int(target_shape[0]), int(target_shape[1])
    if dst_h <= 0 or dst_w <= 0:
        return np.zeros((max(1, dst_h), max(1, dst_w), 4), dtype=np.uint8)
    if (dst_h, dst_w) == (src_h, src_w):
        return image.copy()
    ys = (np.arange(dst_h) * src_h / dst_h).astype(np.int64)
    xs = (np.arange(dst_w) * src_w / dst_w).astype(np.int64)
    ys = np.clip(ys, 0, src_h - 1)
    xs = np.clip(xs, 0, src_w - 1)
    return image[ys[:, None], xs[None, :], :]


def _content_signature(image: np.ndarray, *, size: int) -> tuple:
    """Cheap signature of an image — picks 64 evenly-spaced bytes.

    The :class:`numpy.ndarray` is C-contiguous and uint8 in the
    paint pipeline, so a strided pick is safe to hash. Includes
    ``size`` in the key so changing the requested thumbnail size
    invalidates the cache for that buffer.
    """
    flat = image.reshape(-1)
    sample_count = min(64, flat.size)
    if sample_count == 0:
        return (0, 0, 0, int(size))
    step = max(1, flat.size // sample_count)
    sample = bytes(flat[::step][:sample_count])
    return (image.shape, image.dtype.str, sample, int(size))
