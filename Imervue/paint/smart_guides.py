"""Smart guides + snapping — pure-math snap solver.

Given a candidate point (or rectangle) and a list of snap targets,
return the snapped position plus the targets that activated. The
caller — typically the move-tool dispatcher or the drag handle on
a selection transform — uses the activated-target list to render
"guide tick" overlays so the user sees what they snapped to.

Pure-math; the UI layer wraps these helpers with the actual snap
indicators. ``threshold_px`` controls how close the cursor has to
be before snapping kicks in; default 8 px matches Photoshop's
default smart-guide range.
"""
from __future__ import annotations

from dataclasses import dataclass

SNAP_KINDS = ("vertical", "horizontal")
DEFAULT_SNAP_THRESHOLD = 8


@dataclass(frozen=True)
class SnapTarget:
    """One snappable axis line.

    Vertical targets snap an x-coordinate; horizontal targets snap a
    y-coordinate. ``label`` is a free-form string the UI uses to
    identify the snapped target ("layer 3 left", "document centre",
    "guide #2") when rendering the snap indicator.
    """

    kind: str
    position: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.kind not in SNAP_KINDS:
            raise ValueError(
                f"unknown snap kind {self.kind!r}; expected one of {SNAP_KINDS}",
            )


def snap_point(
    point: tuple[float, float],
    targets: list[SnapTarget],
    *,
    threshold_px: int = DEFAULT_SNAP_THRESHOLD,
) -> tuple[tuple[float, float], list[SnapTarget]]:
    """Snap a point to the nearest target within ``threshold_px``.

    Returns ``((snapped_x, snapped_y), activated_targets)``. Each axis
    is resolved independently — a point may snap horizontally without
    snapping vertically. Exact-distance ties on the same axis are
    broken by encounter order (first wins).
    """
    if threshold_px < 0:
        raise ValueError(f"threshold_px must be >= 0, got {threshold_px}")
    px = float(point[0])
    py = float(point[1])
    activated: list[SnapTarget] = []
    best_x: SnapTarget | None = None
    best_x_dist = float(threshold_px) + 1.0
    best_y: SnapTarget | None = None
    best_y_dist = float(threshold_px) + 1.0
    for target in targets:
        if target.kind == "vertical":
            dist = abs(px - float(target.position))
            if dist < best_x_dist:
                best_x_dist = dist
                best_x = target
        else:
            dist = abs(py - float(target.position))
            if dist < best_y_dist:
                best_y_dist = dist
                best_y = target

    snapped_x = (
        float(best_x.position) if best_x is not None else px
    )
    snapped_y = (
        float(best_y.position) if best_y is not None else py
    )
    if best_x is not None:
        activated.append(best_x)
    if best_y is not None:
        activated.append(best_y)
    return ((snapped_x, snapped_y), activated)


def snap_rect(
    rect: tuple[float, float, float, float],
    targets: list[SnapTarget],
    *,
    threshold_px: int = DEFAULT_SNAP_THRESHOLD,
) -> tuple[tuple[float, float, float, float], list[SnapTarget]]:
    """Snap a rectangle's edges + centre to the nearest targets.

    The rect is described by ``(x, y, w, h)``. Each of the six lines
    (left, centre-x, right, top, centre-y, bottom) is candidate for
    snapping; the snap with the smallest absolute distance per axis
    wins, and the rect translates by that offset. Width and height
    stay unchanged — snapping doesn't resize the rect.
    """
    if threshold_px < 0:
        raise ValueError(f"threshold_px must be >= 0, got {threshold_px}")
    x, y, w, h = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    x_candidates = [x, x + w / 2.0, x + w]
    y_candidates = [y, y + h / 2.0, y + h]

    x_offset, x_target = _best_axis_snap(
        targets, "vertical", x_candidates, threshold_px,
    )
    y_offset, y_target = _best_axis_snap(
        targets, "horizontal", y_candidates, threshold_px,
    )

    activated: list[SnapTarget] = []
    if x_target is not None:
        activated.append(x_target)
    if y_target is not None:
        activated.append(y_target)
    return ((x + x_offset, y + y_offset, w, h), activated)


def _best_axis_snap(
    targets: list[SnapTarget], kind: str,
    candidates: list[float], threshold_px: int,
) -> tuple[float, SnapTarget | None]:
    """Return the smallest snap offset across ``candidates`` against
    every ``kind``-typed target, plus the target that won."""
    best_offset = 0.0
    best_dist = float(threshold_px) + 1.0
    best_target: SnapTarget | None = None
    for target in targets:
        if target.kind != kind:
            continue
        for value in candidates:
            offset = float(target.position) - value
            dist = abs(offset)
            if dist < best_dist:
                best_dist = dist
                best_offset = offset
                best_target = target
    return best_offset, best_target


def targets_from_rect(
    rect: tuple[float, float, float, float],
    *,
    label_prefix: str = "rect",
) -> list[SnapTarget]:
    """Build a six-element snap-target list (left/centre/right +
    top/centre/bottom) from a rectangle. Useful for "snap to this
    layer's bounds" workflows."""
    x, y, w, h = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    cx = x + w / 2.0
    cy = y + h / 2.0
    return [
        SnapTarget(kind="vertical", position=x, label=f"{label_prefix} left"),
        SnapTarget(kind="vertical", position=cx, label=f"{label_prefix} centre"),
        SnapTarget(kind="vertical", position=x + w, label=f"{label_prefix} right"),
        SnapTarget(kind="horizontal", position=y, label=f"{label_prefix} top"),
        SnapTarget(kind="horizontal", position=cy, label=f"{label_prefix} centre"),
        SnapTarget(kind="horizontal", position=y + h, label=f"{label_prefix} bottom"),
    ]
