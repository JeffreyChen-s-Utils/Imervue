"""Expression-adjusted rig evaluation and drawable render caches."""
from __future__ import annotations

from Imervue.puppet.runtime import (
    apply_expressions, compose_all_drawables, resolve_drawable_color,
    resolve_drawable_opacity, resolve_part_state, resolve_pose_visibility,
)


class PuppetCanvasRigMixin:
    """Expression-adjusted rig evaluation and drawable render caches."""

    def _recompute_deformed_vertices(self) -> None:
        if self._document is None:
            self._deformed_vertices = {}
            self._visibility = {}
            self._part_opacity = {}
            self._drawable_opacity = {}
            self._drawable_tint = {}
            return
        active_values = expression_values(self)
        # Physics outputs are layered last, so a chain's output parameter
        # follows the chain even where a slider, motion or expression also
        # sets it.
        active_values = {**active_values, **self._physics_outputs}
        if active_values:
            self._deformed_vertices = compose_all_drawables(
                self._document, active_values,
            )
        else:
            self._deformed_vertices = {}
        # Pose visibility applies even when there are no parameters —
        # users may have a static rig with weapon-swap pose groups.
        pose_visibility = resolve_pose_visibility(
            self._document, self._active_pose,
        )
        # Layer the Part tree's cascading visibility/opacity on top.
        # The renderer reads ``self._visibility`` and the per-drawable
        # opacity, so we fold Part visibility AND with pose visibility
        # and cache the part-opacity multiplier separately.
        part_state = resolve_part_state(self._document)
        merged_visibility: dict[str, bool] = {}
        merged_opacity: dict[str, float] = {}
        for drawable in self._document.drawables:
            pose_vis = pose_visibility.get(drawable.id, bool(drawable.visible))
            part_vis, part_op = part_state.get(drawable.id, (True, 1.0))
            merged_visibility[drawable.id] = pose_vis and part_vis
            merged_opacity[drawable.id] = part_op
        self._visibility = merged_visibility
        self._part_opacity = merged_opacity
        # Pre-compute the per-drawable multiply tint and parameter-driven
        # alpha so paintGL just reads them without rerunning the curves
        # per frame. ``resolve_drawable_opacity`` folds the authored
        # base opacity with every ``opacity_keys`` curve — that's what
        # lets a hidden alternate-pose mesh fade in when its driving
        # parameter (e.g. a wave gesture) fires.
        self._drawable_opacity = {
            drawable.id: resolve_drawable_opacity(drawable, active_values)
            for drawable in self._document.drawables
        }
        self._drawable_tint = {
            drawable.id: resolve_drawable_color(drawable, active_values)
            for drawable in self._document.drawables
        }


def expression_values(canvas) -> dict[str, float]:
    """Authored parameter inputs with the active expression stack applied."""
    return apply_expressions(canvas._parameter_values, canvas._active_expressions)


def refresh_rig(canvas) -> None:
    """Recompose before scheduling a repaint; never redraw a failed evaluation."""
    canvas._recompute_deformed_vertices()
    canvas.update()
