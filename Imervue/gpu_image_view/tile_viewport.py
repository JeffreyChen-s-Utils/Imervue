"""Shared bounded viewport geometry for wall rendering, loading and eviction."""
from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from Imervue.gpu_image_view.tile_layout import tile_grid_layout

if TYPE_CHECKING:
    import numpy as np
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

DEFAULT_TILE_BASE = 256
VIEWPORT_BUFFER = 1


@dataclass(frozen=True)
class TileViewport:
    """A frame's grid geometry and conservative maximum cached tile extent."""

    count: int
    cols: int
    cell: float
    draw_scale: float
    base: float
    width: float
    height: float
    offset_x: float
    offset_y: float
    extent: tuple[float, float]

    def indices(self, *, buffer: int = VIEWPORT_BUFFER) -> Iterator[int]:
        """Yield candidate indices by row/column, without scanning the library."""
        if self.count <= 0 or self.cell <= 0 or self.width <= 0 or self.height <= 0:
            return
        if not all(math.isfinite(v) for v in (
            self.cell, self.offset_x, self.offset_y, *self.extent,
        )):
            return
        pad = max(0, int(buffer))
        first_row, last_row = self._range(
            self.offset_y, self.extent[1], self.height,
            (self.count - 1) // self.cols, pad,
        )
        first_col, last_col = self._range(
            self.offset_x, self.extent[0], self.width, self.cols - 1, pad,
        )
        for row in range(first_row, last_row + 1):
            start = row * self.cols
            for col in range(first_col, min(last_col + 1, self.count - start)):
                yield start + col

    def _range(self, offset, extent, viewport, last, pad):
        low = math.floor((-offset - extent) / self.cell) + 1
        high = math.ceil((viewport - offset) / self.cell) - 1
        return max(0, low - pad), min(last, high + pad)

    def origin(self, index: int) -> tuple[float, float]:
        """Return the screen origin for one model index."""
        row, col = divmod(index, self.cols)
        return col * self.cell + self.offset_x, row * self.cell + self.offset_y


def base_tile_size(view: GPUImageView) -> float:
    """Use the configured thumbnail size, otherwise the first cache sample."""
    size = getattr(view, "thumbnail_size", DEFAULT_TILE_BASE)
    if size is not None:
        return size
    cache = getattr(view, "tile_cache", {})
    if cache:
        shape = getattr(next(iter(cache.values())), "shape", ())
        if len(shape) >= 2:
            return shape[1]
    return DEFAULT_TILE_BASE


def record_tile_extent(view: GPUImageView, image: np.ndarray) -> None:
    """Keep an O(1) conservative extent for decoded images, including large SVGs."""
    shape = getattr(image, "shape", ())
    if len(shape) < 2:
        return
    width, height = getattr(view, "_tile_max_dimensions", (0, 0))
    view._tile_max_dimensions = (max(width, shape[1]), max(height, shape[0]))


def viewport_for(view: GPUImageView) -> TileViewport:
    """Build geometry, or reuse the renderer's immutable current-frame geometry."""
    frame = getattr(view, "_frame_tile_viewport", None)
    if isinstance(frame, TileViewport):
        return frame
    base = base_tile_size(view)
    width = getattr(view, "width", lambda: 512)()
    height = getattr(view, "height", lambda: 512)()
    scale, cell, cols = tile_grid_layout(
        width, base, getattr(view, "tile_scale", 1.),
        getattr(view, "tile_padding", 0.), getattr(view, "devicePixelRatio", lambda: 1.)(),
    )
    dimensions = getattr(view, "_tile_max_dimensions", None)
    if dimensions is None:
        # Legacy/fake views have no tracked extent; inspect the CACHE, never
        # the model list. Production landing paths maintain the bound in O(1).
        shapes = [image.shape[:2] for image in getattr(view, "tile_cache", {}).values()
                  if len(getattr(image, "shape", ())) >= 2]
        dimensions = (max((w for _, w in shapes), default=0),
                      max((h for h, _ in shapes), default=0))
    extent = (max(base, dimensions[0]) * scale, max(base, dimensions[1]) * scale)
    return TileViewport(
        len(view.model.images), cols, cell, scale, base, width, height,
        getattr(view, "grid_offset_x", 0.), getattr(view, "grid_offset_y", 0.), extent,
    )
