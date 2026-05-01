"""Cubic Bézier path data + sampling for the pen tool.

The pen tool builds a polyline of :class:`PathNode` instances —
each one carries the on-curve anchor plus the two off-curve
handles (incoming and outgoing). :func:`sample_path` walks the
nodes pairwise and evaluates the cubic Bézier between them at a
configurable resolution; the result is a flat list of ``(x, y)``
samples that the rasteriser (or :mod:`vector_layer`) can stamp
through.

Pure-math, Qt-free. The interactive pen tool that drives node
placement lives in :mod:`tool_dispatcher`; this module owns the
data + evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_SAMPLES_PER_SEGMENT = 24
MAX_SAMPLES_PER_SEGMENT = 2048


@dataclass(frozen=True)
class PathNode:
    """One on-curve anchor + its two control handles.

    ``handle_in`` controls the curve approaching this node from the
    previous one; ``handle_out`` controls the curve leaving toward
    the next node. ``None`` means "no handle", which the sampler
    treats as the anchor itself — i.e. a straight segment on that
    side.
    """

    anchor: tuple[float, float]
    handle_in: tuple[float, float] | None = None
    handle_out: tuple[float, float] | None = None

    def to_dict(self) -> dict:
        return {
            "anchor": list(self.anchor),
            "handle_in": list(self.handle_in) if self.handle_in else None,
            "handle_out": list(self.handle_out) if self.handle_out else None,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> PathNode:
        if not isinstance(raw, dict):
            raise ValueError(
                f"node payload must be a dict, got {type(raw).__name__}",
            )
        anchor = _safe_pair(raw.get("anchor"), default=(0.0, 0.0))
        return cls(
            anchor=anchor,
            handle_in=_safe_pair(raw.get("handle_in"), default=None),
            handle_out=_safe_pair(raw.get("handle_out"), default=None),
        )


@dataclass
class BezierPath:
    """Mutable list of :class:`PathNode` plus a closed flag."""

    nodes: list[PathNode] = field(default_factory=list)
    closed: bool = False

    def append(self, node: PathNode) -> None:
        self.nodes.append(node)

    def insert(self, index: int, node: PathNode) -> None:
        if not 0 <= index <= len(self.nodes):
            raise IndexError(f"insert index {index} out of range")
        self.nodes.insert(index, node)

    def remove(self, index: int) -> bool:
        if not 0 <= index < len(self.nodes):
            return False
        del self.nodes[index]
        return True

    def replace(self, index: int, node: PathNode) -> bool:
        if not 0 <= index < len(self.nodes):
            return False
        self.nodes[index] = node
        return True

    def to_dict(self) -> dict:
        return {
            "closed": bool(self.closed),
            "nodes": [n.to_dict() for n in self.nodes],
        }

    @classmethod
    def from_dict(cls, raw: dict) -> BezierPath:
        if not isinstance(raw, dict):
            return cls()
        nodes_raw = raw.get("nodes") or []
        nodes: list[PathNode] = []
        if isinstance(nodes_raw, list):
            for entry in nodes_raw:
                try:
                    nodes.append(PathNode.from_dict(entry))
                except (ValueError, TypeError):
                    continue
        return cls(nodes=nodes, closed=bool(raw.get("closed", False)))


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def sample_path(
    path: BezierPath,
    *,
    samples_per_segment: int = DEFAULT_SAMPLES_PER_SEGMENT,
) -> list[tuple[float, float]]:
    """Evaluate ``path`` to a flat list of ``(x, y)`` samples.

    Each segment between consecutive nodes is sampled
    ``samples_per_segment`` times (inclusive of both endpoints, so
    consecutive segments don't visually duplicate the join point).
    Empty / single-node paths return an empty list.
    """
    if samples_per_segment < 2:
        raise ValueError(
            f"samples_per_segment must be >= 2, got {samples_per_segment!r}",
        )
    if samples_per_segment > MAX_SAMPLES_PER_SEGMENT:
        raise ValueError(
            f"samples_per_segment must be <= {MAX_SAMPLES_PER_SEGMENT}, "
            f"got {samples_per_segment!r}",
        )
    if len(path.nodes) < 2:
        return []
    pairs = list(zip(path.nodes, path.nodes[1:], strict=False))
    if path.closed:
        pairs.append((path.nodes[-1], path.nodes[0]))
    out: list[tuple[float, float]] = []
    for index, (a, b) in enumerate(pairs):
        # Skip the leading endpoint of every segment except the first
        # so consecutive segments share their join sample exactly.
        first = 0 if index == 0 else 1
        for step in range(first, samples_per_segment + 1):
            t = step / samples_per_segment
            out.append(_eval_segment(a, b, t))
    return out


def _eval_segment(
    a: PathNode, b: PathNode, t: float,
) -> tuple[float, float]:
    """Cubic Bézier point at ``t`` on the segment from ``a`` to ``b``.

    The control points are the anchors plus the relevant handles; a
    missing handle collapses to the anchor itself, turning that side
    of the curve into a straight line so a "no-handle" node behaves
    like a corner point.
    """
    p0 = a.anchor
    p3 = b.anchor
    p1 = a.handle_out if a.handle_out is not None else a.anchor
    p2 = b.handle_in if b.handle_in is not None else b.anchor
    omt = 1.0 - t
    omt2 = omt * omt
    t2 = t * t
    bx = (
        omt2 * omt * p0[0]
        + 3.0 * omt2 * t * p1[0]
        + 3.0 * omt * t2 * p2[0]
        + t2 * t * p3[0]
    )
    by = (
        omt2 * omt * p0[1]
        + 3.0 * omt2 * t * p1[1]
        + 3.0 * omt * t2 * p2[1]
        + t2 * t * p3[1]
    )
    return (bx, by)


# ---------------------------------------------------------------------------
# Hit testing — for the pen tool's drag-anchor / drag-handle UX
# ---------------------------------------------------------------------------


def nearest_node(
    path: BezierPath, point: tuple[float, float], *, max_distance: float = 8.0,
) -> int | None:
    """Return the index of the anchor nearest to ``point``, or ``None``
    if no anchor is within ``max_distance``."""
    px, py = float(point[0]), float(point[1])
    best_index: int | None = None
    best_dist_sq = max_distance * max_distance
    for index, node in enumerate(path.nodes):
        ax, ay = node.anchor
        dist_sq = (ax - px) ** 2 + (ay - py) ** 2
        if dist_sq <= best_dist_sq:
            best_index = index
            best_dist_sq = dist_sq
    return best_index


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_pair(value, *, default):
    """Coerce a JSON-friendly entry into a ``(x, y)`` tuple."""
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return (float(value[0]), float(value[1]))
        except (TypeError, ValueError):
            return default
    return default
