"""Deformer selection and vertex editing gestures."""
from __future__ import annotations

from Imervue.puppet.canvas_rig import refresh_rig

from Imervue.puppet.mesh_edit import find_drawable_at, move_vertex
from Imervue.puppet.render_prep import build_draw_list


class PuppetCanvasEditingMixin:
    """Deformer selection and vertex editing gestures."""

    def selected_deformer(self) -> str | None:
        return self._selected_deformer

    def set_selected_deformer(self, deformer_id: str | None) -> None:
        """Pick which deformer the editor wants highlighted on canvas.
        The selection overlay draws an anchor marker plus a bounding
        box around the targeted drawables so the user can see what
        the bone tree click referred to. An empty string is treated
        the same as ``None`` so callers that pump signal payloads
        through can clear via either spelling."""
        new_value = (
            deformer_id if isinstance(deformer_id, str) and deformer_id else None
        )
        if new_value == self._selected_deformer:
            return
        self._selected_deformer = new_value
        self.update()

    def clear_selection(self) -> None:
        """Drop the selection overlay. Convenience wrapper used by the
        right-click clear path; equivalent to ``set_selected_deformer(None)``
        followed by emitting :attr:`selection_cleared`."""
        if self._selected_deformer is None:
            return
        self._selected_deformer = None
        self.update()
        self.selection_cleared.emit()

    def set_mesh_edit_enabled(self, enabled: bool) -> None:
        """Toggle the click-to-drag vertex editor. Switching off also
        clears any active drag target."""
        self._mesh_edit_enabled = bool(enabled)
        if not enabled:
            self._mesh_edit_target = None

    def mesh_edit_enabled(self) -> bool:
        return self._mesh_edit_enabled

    def begin_mesh_edit_at(self, image_x: float, image_y: float) -> bool:
        """Pick the topmost vertex within the snap radius of ``(image_x,
        image_y)`` and start a drag. Returns ``True`` if a vertex was
        grabbed."""
        if not self._mesh_edit_enabled or self._document is None:
            return False
        hit = find_drawable_at(self._document, image_x, image_y)
        self._mesh_edit_target = hit
        return hit is not None

    def update_mesh_edit_drag(self, image_x: float, image_y: float) -> bool:
        """Move the grabbed vertex to ``(image_x, image_y)`` and rebuild
        the draw list so the renderer picks up the change."""
        if not self._mesh_edit_enabled or self._mesh_edit_target is None:
            return False
        if self._document is None:
            return False
        drawable_id, vertex_idx = self._mesh_edit_target
        drawable = self._document.drawable(drawable_id)
        if drawable is None:
            return False
        if not move_vertex(drawable, vertex_idx, image_x, image_y):
            return False
        self._draw_list = build_draw_list(self._document)
        refresh_rig(self)
        return True

    def end_mesh_edit_drag(self) -> None:
        self._mesh_edit_target = None
