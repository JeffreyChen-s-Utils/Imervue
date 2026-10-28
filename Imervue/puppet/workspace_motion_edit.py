"""Active motion timeline editing and hit-area playback routing."""
from __future__ import annotations
from Imervue.puppet.motion_timeline import MotionTimelineDialog

class PuppetMotionEditMixin:
    def _edit_active_motion(self) -> None:
        player = self._motion_dock.player()
        motion = player.motion()
        if motion is None:
            self._announce(
                "puppet_no_active_motion",
                "Pick a motion from the dock before editing.",
            )
            return
        doc = self._canvas.document()
        ranges = {p.id: (p.min, p.max) for p in doc.parameters} if doc is not None else {}
        dialog = MotionTimelineDialog(motion, self, ranges=ranges)
        dialog.widget().track_modified.connect(self._on_timeline_edit_committed)
        dialog.exec()

    def _on_timeline_edit_committed(self) -> None:
        """Force the player to re-apply the (now edited) motion at the
        current playhead so the canvas reflects the new curve without
        needing the user to press Play."""
        player = self._motion_dock.player()
        if player.motion() is None:
            return
        player.seek(player.elapsed())

    def _on_hit_area_triggered(self, area_id: str) -> None:
        """Canvas → workspace bridge. Looks up the hit area, plays its
        motion through the motion dock's player (if any), and toggles
        its expression on the canvas (if any). Either is optional —
        a hit area can fire only one of the two."""
        doc = self._canvas.document()
        if doc is None:
            return
        area = next((h for h in doc.hit_areas if h.id == area_id), None)
        if area is None:
            return
        if area.motion:
            if any(m.group == area.motion for m in doc.motions):
                # Treat the HitArea.motion field as a group name when
                # any motion is tagged with it — matches Cubism's
                # "TapHead" / "TapBody" convention.
                self._motion_dock.player().play_group(area.motion, doc.motions)
            elif self._motion_dock.select_motion(area.motion):
                self._motion_dock.player().play()
        if area.expression:
            if area.expression in self._canvas.active_expressions():
                self._canvas.remove_expression(area.expression)
            else:
                self._canvas.add_expression(area.expression)
        self._announce(
            "puppet_hit_area_triggered", "Hit area '{id}' triggered",
            id=area_id,
        )
