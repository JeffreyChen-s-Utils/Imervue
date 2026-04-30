"""Vector strokes — non-destructive line layer.

Raster layers store finished pixels; vector layers store the strokes
themselves so the user can re-edit them later (move a control point,
change line width / colour, delete a stroke). The trade-off is the
extra rasterisation cost on every composite — kept manageable by
caching the rasterised image on the layer until the stroke list
changes.

A :class:`VectorStroke` is a polyline (list of control points) with
a uniform width + colour. Anti-aliased rasterisation is provided by
:func:`rasterise_strokes` which walks each segment and stamps a
disc-shaped kernel along the path; the kernel matches what
``round_brush_kernel`` produces so the visual style stays consistent
with the raster brush.

The module is Qt-free and operates on plain numpy arrays so it can
be unit-tested without a display server. The integration with
:class:`Imervue.paint.document.PaintDocument` lives in
:mod:`Imervue.paint.compositing` (the compositor checks
``Layer.vector_strokes`` and routes to the rasteriser).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DEFAULT_VECTOR_WIDTH = 4.0
DEFAULT_VECTOR_COLOR = (0, 0, 0, 255)


@dataclass(frozen=True)
class VectorStroke:
    """A polyline stroke — points, width, colour, opacity.

    ``points`` is the ordered list of (x, y) control points. The
    rasteriser draws an anti-aliased line through them by stamping a
    disc-shaped kernel at each interpolated position. ``width`` is the
    stroke diameter in pixels (matches the raster brush's ``size``
    parameter). ``opacity`` is in [0, 1].

    Empty / single-point strokes still rasterise — a single point
    stamps one dab so the user sees something at the click location.
    """

    points: tuple[tuple[float, float], ...]
    width: float = DEFAULT_VECTOR_WIDTH
    color: tuple[int, int, int, int] = DEFAULT_VECTOR_COLOR
    opacity: float = 1.0

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError(f"width must be positive, got {self.width!r}")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError(
                f"opacity must be in [0, 1], got {self.opacity!r}",
            )
        if len(self.color) != 4 or any(
            not 0 <= int(c) <= 255 for c in self.color
        ):
            raise ValueError(
                f"color must be a 4-tuple of 0..255 ints, got {self.color!r}",
            )

    def to_dict(self) -> dict:
        return {
            "points": [list(p) for p in self.points],
            "width": float(self.width),
            "color": list(self.color),
            "opacity": float(self.opacity),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> VectorStroke:
        raw_points = raw.get("points", ())
        points: list[tuple[float, float]] = []
        if isinstance(raw_points, (list, tuple)):
            for entry in raw_points:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    try:
                        points.append((float(entry[0]), float(entry[1])))
                    except (TypeError, ValueError):
                        continue
        return cls(
            points=tuple(points),
            width=float(raw.get("width", DEFAULT_VECTOR_WIDTH)),
            color=tuple(
                max(0, min(255, int(c))) for c in raw.get(
                    "color", DEFAULT_VECTOR_COLOR,
                )
            ),
            opacity=max(0.0, min(1.0, float(raw.get("opacity", 1.0)))),
        )


@dataclass
class VectorLayerData:
    """Mutable container for a vector layer's stroke list.

    Layers stored on :class:`PaintDocument` are dataclass instances,
    so attaching a *mutable* container rather than putting strokes
    directly on the layer keeps the dataclass-comparison invariants
    intact. The compositor consults this container's strokes when
    rendering, and the rasterisation cache lives here too so multiple
    composites don't re-rasterise unchanged geometry.
    """

    strokes: list[VectorStroke] = field(default_factory=list)
    _cache: np.ndarray | None = None

    def add(self, stroke: VectorStroke) -> None:
        self.strokes.append(stroke)
        self._cache = None

    def remove(self, index: int) -> bool:
        if not 0 <= index < len(self.strokes):
            return False
        del self.strokes[index]
        self._cache = None
        return True

    def replace(self, index: int, stroke: VectorStroke) -> bool:
        if not 0 <= index < len(self.strokes):
            return False
        self.strokes[index] = stroke
        self._cache = None
        return True

    def clear(self) -> None:
        self.strokes.clear()
        self._cache = None

    def invalidate_cache(self) -> None:
        self._cache = None

    def render(self, shape: tuple[int, int]) -> np.ndarray:
        """Return the rasterised RGBA image, using the cache if present.

        ``shape`` is ``(height, width)``. A shape mismatch invalidates
        the cache automatically so resizing the canvas re-renders.
        """
        if (
            self._cache is not None
            and self._cache.shape[:2] == shape
        ):
            return self._cache
        out = np.zeros((shape[0], shape[1], 4), dtype=np.uint8)
        rasterise_strokes(out, self.strokes)
        self._cache = out
        return out


# ---------------------------------------------------------------------------
# Rasterisation
# ---------------------------------------------------------------------------


def rasterise_strokes(
    canvas: np.ndarray,
    strokes,
) -> None:
    """Paint each stroke onto ``canvas`` (HxWx4 uint8) in place.

    Strokes are composited bottom-up using normal alpha blending.
    Each stroke is rendered by interpolating along its segments and
    stamping a soft round kernel at each step; spacing is set to a
    quarter of the stroke width so straight lines don't show gaps.
    """
    if canvas.ndim != 3 or canvas.shape[2] != 4 or canvas.dtype != np.uint8:
        raise ValueError(
            f"canvas must be HxWx4 uint8 RGBA, got {canvas.shape} {canvas.dtype}",
        )
    for stroke in strokes:
        _rasterise_one(canvas, stroke)


def realise_vector_layer(layer) -> bool:
    """Repaint ``layer.image`` from ``layer.vector_data.strokes``.

    Returns ``True`` if the layer actually has vector data — callers
    use the bool to skip the no-op for raster layers. The image is
    completely overwritten (zeroed first, then strokes painted on top)
    so removing a stroke shrinks the visible content correctly.
    """
    data = getattr(layer, "vector_data", None)
    if data is None:
        return False
    h, w = layer.image.shape[:2]
    rendered = data.render((h, w))
    np.copyto(layer.image, rendered)
    return True


def _rasterise_one(canvas: np.ndarray, stroke: VectorStroke) -> None:
    if not stroke.points:
        return
    from Imervue.paint.brush_engine import apply_dab, round_brush_kernel
    size = max(1, int(round(stroke.width)))
    kernel = round_brush_kernel(size, hardness=0.7)
    color_rgb = (int(stroke.color[0]), int(stroke.color[1]), int(stroke.color[2]))
    spacing = max(1.0, stroke.width * 0.25)

    if len(stroke.points) == 1:
        x, y = stroke.points[0]
        apply_dab(
            canvas, float(x), float(y), kernel, color_rgb,
            opacity=stroke.opacity,
        )
        return

    # Stamp the first point exactly once, then march along each segment.
    apply_dab(
        canvas, float(stroke.points[0][0]), float(stroke.points[0][1]),
        kernel, color_rgb, opacity=stroke.opacity,
    )
    for (x0, y0), (x1, y1) in zip(stroke.points[:-1], stroke.points[1:], strict=False):
        dx = float(x1) - float(x0)
        dy = float(y1) - float(y0)
        distance = math.hypot(dx, dy)
        if distance <= spacing:
            apply_dab(
                canvas, float(x1), float(y1), kernel, color_rgb,
                opacity=stroke.opacity,
            )
            continue
        n_steps = int(math.ceil(distance / spacing))
        for i in range(1, n_steps + 1):
            t = i / n_steps
            apply_dab(
                canvas,
                float(x0) + dx * t,
                float(y0) + dy * t,
                kernel, color_rgb,
                opacity=stroke.opacity,
            )
