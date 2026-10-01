"""Commit the workspace's bezier pen path to the active layer.

Wraps :func:`Imervue.paint.stroke_along_path.stroke_along_path` with
the workspace-side bookkeeping the canvas needs:

* turns the workspace's active brush settings into a
  :class:`BrushStrokeOptions`,
* paints onto the active layer's image buffer,
* invalidates the document composite so the canvas re-uploads,
* clears the workspace's stored path so a fresh pen session
  starts cleanly.

Pure-numpy / Qt-free; the canvas widget calls
:func:`commit_pen_path` from a key handler (Enter / Return) and
from the dispatcher's double-click path.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.paint.brush_engine import BrushStrokeOptions

#: Points per anchor-to-anchor span of a Smooth pen curve; fine enough that the
#: straight steps between them do not show at painting zoom levels.
SMOOTH_SAMPLES_PER_SEGMENT = 24

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def commit_pen_path(workspace: PaintWorkspace) -> bool:
    """Rasterise the workspace's active bezier path onto the layer.

    Returns ``True`` if anything was actually committed; ``False``
    when there's no active path, no active layer, the path has
    fewer than two anchors (a single click never produces a stroke),
    or the foreground slot is set to "transparent" — there's no
    colour to deposit so the commit is a no-op.
    """
    path = getattr(workspace, "_bezier_pen_path", None)
    if path is None or len(path.nodes) < 2:
        return False
    document = workspace.canvas().document()
    layer = document.active_layer()
    if layer is None:
        return False
    state = workspace.state()
    if state.foreground is None:
        return False
    drawn = smoothed_path(path) if state.pen_smooth else path
    # Vector layer → record the path as a non-destructive VectorStroke
    # so the user can edit width / colour / per-node geometry later
    # rather than baking pixels in.
    if getattr(layer, "vector_data", None) is not None:
        committed = _commit_to_vector_layer(drawn, layer, state)
    else:
        committed = _commit_to_raster_layer(drawn, layer, state)
    # Reset the path so the next pen click starts a fresh stroke.
    path.nodes.clear()
    path.closed = False
    document.invalidate_composite()
    return committed


def smooth_points(path) -> list[tuple[float, float]]:
    """The Pen's Smooth curve through *path*'s anchors (Catmull-Rom), closed if the path is."""
    from Imervue.paint.catmull_rom_spline import resample_polyline_catmull_rom
    anchors = [(float(n.anchor[0]), float(n.anchor[1])) for n in path.nodes]
    return resample_polyline_catmull_rom(anchors, closed=bool(path.closed),
                                         samples_per_segment=SMOOTH_SAMPLES_PER_SEGMENT)


def smoothed_path(path):
    """A path of straight steps along :func:`smooth_points`, ready for the usual rasterising.

    The anchors' own handles are not used: Smooth draws one curve through every
    clicked point.
    """
    from Imervue.paint.bezier_path import BezierPath, PathNode
    nodes = [PathNode(anchor=point) for point in smooth_points(path)]
    return BezierPath(nodes=nodes, closed=bool(path.closed))


def _commit_to_raster_layer(path, layer, state) -> bool:
    options = _options_from_state(state)
    from Imervue.paint.stroke_along_path import stroke_along_path
    damage = stroke_along_path(layer.image, path, options)
    return not damage.is_empty


def _commit_to_vector_layer(path, layer, state) -> bool:
    """Convert the bezier path's anchors into a :class:`VectorStroke`
    and append it to the layer's vector data.

    Bezier handles are flattened to a polyline at commit time —
    the editable storage stays as a polyline (one VectorStroke per
    pen session) so existing rasteriser code works unchanged. A
    future revision can promote the VectorStroke model to true
    bezier curves once we have a UI for editing handles.
    """
    from Imervue.paint.vector_layer import VectorStroke
    points = tuple((float(n.anchor[0]), float(n.anchor[1])) for n in path.nodes)
    brush = state.brush
    fg = tuple(int(c) for c in state.foreground)
    color = (fg[0], fg[1], fg[2], 255)
    stroke = VectorStroke(
        points=points,
        width=max(1.0, float(brush.size)),
        color=color,
        opacity=float(brush.opacity),
    )
    layer.vector_data.add(stroke)
    return True


def _options_from_state(state) -> BrushStrokeOptions:
    """Build a :class:`BrushStrokeOptions` from the workspace state.

    The pen tool reuses the brush settings rather than introducing
    a separate "pen size / pen colour" axis — matches raster paint apps'
    "your active brush is your pen ink" convention.
    """
    brush = state.brush
    return BrushStrokeOptions(
        color=tuple(state.foreground),
        size=int(brush.size),
        opacity=float(brush.opacity),
        hardness=float(brush.hardness),
        blend_mode=str(brush.blend_mode),
    )
