"""Workspace neutral-state restoration and driver shutdown."""
from __future__ import annotations
import logging
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.best_effort import best_effort

logger = logging.getLogger("Imervue.plugin.puppet.workspace")

class PuppetResetMixin:
    def _reset_to_rest(self) -> None:
        """Snap the rig back to its authored neutral pose.

        Motions don't auto-rewind on stop — when a clip finishes (or
        the user pauses one mid-play) the rig stays frozen wherever
        the last sample landed. Combined with the live-input toggles
        (auto-blink, drag-track, lip-sync, webcam …) the user can
        easily end up with the puppet stuck in a weird half-pose with
        no obvious "go back to neutral" button. This method is that
        button.

        Order is deliberate: stop the *producers* first (motion
        player, live drivers, recorder, idle cycler) so they can't
        immediately overwrite the values we're about to reset; then
        clear the *state* (expressions, pose groups, physics outputs);
        finally restore the parameter dict to authored defaults.
        """
        # 1. Stop the motion player without playing out its fade.
        player = self._motion_dock.player() if hasattr(self, "_motion_dock") else None
        if player is not None and (player.is_playing() or player.is_fading_out()):
            player._snap_stop()   # noqa: SLF001 — bypass fade for a hard reset
        # 2. Untoggle every live-input action. setChecked(False) fires
        #    the connected ``_toggle_*`` slot which is exactly the
        #    teardown path we want.
        for toggle in (
            getattr(self, "_drag_toggle", None),
            getattr(self, "_blink_toggle", None),
            getattr(self, "_lipsync_toggle", None),
            getattr(self, "_webcam_toggle", None),
            getattr(self, "_idle_toggle", None),
            getattr(self, "_idle_motion_toggle", None),
            getattr(self, "_motion_record_toggle", None),
        ):
            if toggle is not None and toggle.isChecked():
                toggle.setChecked(False)
        # 3. Drop expressions + pose-group overrides + physics outputs.
        for name in self._canvas.active_expressions():
            self._canvas.remove_expression(name)
        # The canvas's pose-group dict is exposed via active_pose();
        # call set_pose_active with the empty default for each group.
        doc = self._canvas.document()
        if doc is not None:
            for group in doc.pose_groups:
                if group.drawables:
                    # Restore the group's first drawable as the visible
                    # member — matches resolve_pose_visibility's
                    # "default to first member" semantics.
                    self._canvas.set_pose_active(group.id, group.drawables[0])
        self._canvas.reset_physics()
        # 4. Snap parameters back to their authored defaults.
        self._canvas.reset_parameters()
        # 5. Status feedback so the user sees the action took effect.
        lang = language_wrapper.language_word_dict
        self._status.setText(
            lang.get("puppet_status_reset", "Rig reset to neutral pose."),
        )

    def _shutdown_drivers(self) -> None:
        """Stop every live-capture / output driver.

        Webcam tracking and mic lip-sync hold OS devices (``cv2.VideoCapture`` /
        a sounddevice stream) open and run background callbacks against the
        canvas. Without this, closing the workspace left the camera + mic locked
        until process exit, and the mic's ``_on_audio_block`` fired on the now
        deleted ``PuppetCanvas`` (``RuntimeError: Internal C++ object already
        deleted``). Each ``shutdown`` is guarded so one failing driver still lets
        the rest stop; the failure is logged with the driver's class name.
        """
        for driver in (
            getattr(self, "_webcam", None),
            getattr(self, "_input_engine", None),
            getattr(self, "_virtual_camera", None),
            getattr(self, "_ndi_output", None),
        ):
            if driver is not None:
                with best_effort(f"shut down {type(driver).__name__}", logger):
                    driver.shutdown()
