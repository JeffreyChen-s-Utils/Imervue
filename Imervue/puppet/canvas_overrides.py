"""Authored expression stack and pose selection."""
from __future__ import annotations

from Imervue.puppet.canvas_rig import refresh_rig


class PuppetCanvasOverridesMixin:
    """Authored expression stack and pose selection."""

    def add_expression(self, name: str) -> bool:
        """Push an expression by name onto the active stack. No-op if
        the document doesn't have that expression or it's already on."""
        if self._document is None:
            return False
        match = next(
            (e for e in self._document.expressions if e.name == name), None,
        )
        if match is None:
            return False
        if name in self.active_expressions():
            return False
        self._active_expressions.append(match)
        refresh_rig(self)
        return True

    def remove_expression(self, name: str) -> bool:
        before = len(self._active_expressions)
        self._active_expressions = [
            e for e in self._active_expressions if e.name != name
        ]
        if len(self._active_expressions) == before:
            return False
        refresh_rig(self)
        return True

    def active_expressions(self) -> list[str]:
        return [e.name for e in self._active_expressions]

    def set_pose_active(self, group_id: str, drawable_id: str) -> bool:
        """Pick which drawable in a pose group is currently visible."""
        if self._document is None:
            return False
        group = next(
            (g for g in self._document.pose_groups if g.id == group_id), None,
        )
        if group is None or drawable_id not in group.drawables:
            return False
        self._active_pose[group_id] = drawable_id
        refresh_rig(self)
        self.pose_changed.emit(group_id, drawable_id)
        return True

    def active_pose(self) -> dict[str, str]:
        return dict(self._active_pose)

    def visibility(self) -> dict[str, bool]:
        return dict(self._visibility)
