"""Live inputs and outputs of the puppet workspace.

Recording the canvas to video, webcam face tracking with its preview,
the system virtual camera, NDI output and the VTube Studio API, each toggled
from the toolbar with its optional dependency offered for install on first
use. ``PuppetWorkspace`` mixes these methods in.
"""
from __future__ import annotations

from pathlib import Path

from OpenGL.error import GLError
from PySide6.QtWidgets import QFileDialog

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.recorder import write_canvas_png
from Imervue.puppet.webcam_status import WebcamPhase, status_text
from Imervue.gui.background_jobs import job_registry
from Imervue.system.job_state import JobState
from Imervue.puppet.requirements import (
    NDI_PACKAGES,
    VIRTUAL_CAMERA_PACKAGES,
    WEBCAM_PACKAGES,
    missing_packages,
)


_RECORD_TITLE_KEY = "puppet_record_dialog_title"
_RECORD_TITLE = "Record Animation"


class PuppetLiveMixin:
    """Recording, webcam tracking and streaming outputs of the puppet workspace."""

    def _capture_via_dialog(self) -> None:
        if self._canvas.document() is None:
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("puppet_capture_dialog_title", "Capture Frame"),
            "",
            "PNG (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path = f"{path}.png"
        error = ""
        try:
            write_canvas_png(self._canvas, path)
        except (GLError, RuntimeError, OSError) as exc:
            error = str(exc) or type(exc).__name__
        self._retain_output_result("puppet_capture_dialog_title", "Capture Frame", path, error)
        if error:
            self._announce("puppet_capture_error", "Capture failed: {error}", error=error)
        else:
            self._announce(
                "puppet_capture_saved", "Saved frame to {name}",
                name=str(Path(path).absolute()),
            )

    def _toggle_recording(self, enabled: bool) -> None:
        if enabled:
            self._start_recording()
        else:
            self._recorder.stop()

    def _start_recording(self) -> None:
        if self._recorder.is_recording():
            return
        if self._canvas.document() is None:
            self._record_action.setChecked(False)
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get(_RECORD_TITLE_KEY, _RECORD_TITLE),
            "",
            "GIF (*.gif);;WebM (*.webm);;MP4 (*.mp4)",
        )
        if not path:
            self._record_action.setChecked(False)
            return
        self._recording_destination = str(Path(path).absolute())
        self._recording_job = job_registry().add_activity(
            lang.get(_RECORD_TITLE_KEY, _RECORD_TITLE),
            JobState([self._recording_destination]), self._recorder.stop,
        )
        ok = self._recorder.start(path)
        if not ok:
            self._record_action.setChecked(False)

    def _on_recording_finished(self, path: str) -> None:
        self._finish_recording_result(path)
        self._announce(
            "puppet_record_saved", "Recording saved to {name}",
            name=str(Path(path).absolute()),
        )
        self._record_action.blockSignals(True)
        self._record_action.setChecked(False)
        self._record_action.blockSignals(False)

    def _on_recording_failed(self, reason: str) -> None:
        path = getattr(self, "_recording_destination", "")
        self._finish_recording_result(path, reason)
        self._announce(
            "puppet_record_failed", "Recording failed: {error}",
            error=reason,
        )
        self._record_action.blockSignals(True)
        self._record_action.setChecked(False)
        self._record_action.blockSignals(False)

    def _finish_recording_result(self, path: str, error: str = "") -> None:
        job = getattr(self, "_recording_job", None)
        if job is None:
            self._retain_output_result(
                _RECORD_TITLE_KEY, _RECORD_TITLE, path, error,
            )
        else:
            source = self._recording_destination
            job.state.record(source, output=str(Path(path).absolute()) if not error else "",
                             error=error)
            job.state.finish()
            job.cancel_callback = None
            job_registry().poll()
        self._recording_job = None
        self._recording_destination = ""

    @staticmethod
    def _retain_output_result(key: str, title: str, path: str, error: str = "") -> None:
        title = language_wrapper.language_word_dict.get(key, title)
        source = str(Path(path).absolute()) if path else title
        state = JobState([source])
        state.record(source, output=source if not error else "", error=error)
        state.finish()
        job_registry().add_completed(title, state)

    def _toggle_webcam(self, enabled: bool) -> None:
        if enabled and missing_packages(WEBCAM_PACKAGES):
            self._prompt_install(
                WEBCAM_PACKAGES,
                # Re-fire the toggle once pip is done; the dependency
                # check on the second pass returns an empty list, so we
                # fall through into the real enable path.
                on_ready=lambda: self._webcam_toggle.setChecked(True),
            )
            self._reset_toggle(self._webcam_toggle)
            return
        self._webcam.set_enabled(enabled)
        self._on_webcam_state_changed()
        # Pop a live preview window so the user can see what the
        # camera is producing. The dialog polls the tracker via timer;
        # we keep one instance around to avoid re-creating it every
        # time the user re-toggles.
        if enabled:
            self._show_webcam_preview()
        else:
            self._hide_webcam_preview()

    def _on_webcam_state_changed(self) -> None:
        status = self._webcam.status()
        toggle = getattr(self, "_webcam_toggle", None)
        if toggle is not None:
            toggle.blockSignals(True)
            toggle.setChecked(status.active)
            toggle.setEnabled(status.phase != WebcamPhase.STOPPING)
            toggle.setToolTip(status_text(status, language_wrapper.language_word_dict))
            toggle.blockSignals(False)

    def _install_webcam_packages(self) -> None:
        self._prompt_install(WEBCAM_PACKAGES, on_ready=lambda: self._toggle_webcam(True))

    def _show_webcam_preview(self) -> None:
        from Imervue.puppet.webcam_preview_dialog import WebcamPreviewDialog
        if getattr(self, "_webcam_preview_dialog", None) is None:
            dlg = WebcamPreviewDialog(self._webcam, self)
            dlg.install_requested.connect(self._install_webcam_packages)
            # Closing the dialog (X button or "Stop tracking") needs to
            # also untick the toolbar toggle — otherwise the toggle
            # stays "on" while the tracker is actually stopped.
            dlg.finished.connect(self._on_webcam_preview_finished)
            self._webcam_preview_dialog = dlg
        self._webcam_preview_dialog.show()
        self._webcam_preview_dialog.raise_()
        self._webcam_preview_dialog.activateWindow()

    def _hide_webcam_preview(self) -> None:
        dlg = getattr(self, "_webcam_preview_dialog", None)
        if dlg is not None:
            dlg.hide()

    def _on_webcam_preview_finished(self, _result: int) -> None:
        # User closed the preview dialog directly. ``set_enabled`` is
        # idempotent so the back-and-forth between this slot and the
        # dialog's ``closeEvent`` settles after one round.
        if self._webcam_toggle.isChecked():
            self._reset_toggle(self._webcam_toggle)

    def _toggle_virtual_camera(self, enabled: bool) -> None:
        if enabled and missing_packages(VIRTUAL_CAMERA_PACKAGES):
            self._prompt_install(
                VIRTUAL_CAMERA_PACKAGES,
                on_ready=lambda: self._virtual_camera_toggle.setChecked(True),
            )
            self._reset_toggle(self._virtual_camera_toggle)
            return
        ok = self._virtual_camera.set_enabled(enabled)
        if enabled and not ok:
            self._reset_toggle(self._virtual_camera_toggle)
            self._announce(
                "puppet_virtual_camera_failed",
                "Virtual camera unavailable (install pyvirtualcam + OBS Virtual Camera).",
            )
            return
        if enabled:
            # Once a frame has flown, the camera object knows which
            # device name pyvirtualcam handed back (OBS Virtual
            # Camera / Unity Capture / v4l2loopback). Echo it so the
            # user knows exactly what to pick in OBS's source list.
            cam = getattr(self._virtual_camera, "_camera", None)
            device = getattr(cam, "device", None) if cam is not None else None
            self._announce(
                "puppet_virtual_camera_on",
                'Streaming as "{device}" — add it as a Video Capture Device in OBS.',
                device=device or "OBS Virtual Camera",
            )
        else:
            self._announce(
                "puppet_virtual_camera_off", "Virtual camera off",
            )

    def _toggle_ndi(self, enabled: bool) -> None:
        if enabled and missing_packages(NDI_PACKAGES):
            self._prompt_install(
                NDI_PACKAGES,
                on_ready=lambda: self._ndi_toggle.setChecked(True),
            )
            self._reset_toggle(self._ndi_toggle)
            return
        ok = self._ndi_output.set_enabled(enabled)
        if enabled and not ok:
            self._reset_toggle(self._ndi_toggle)
            self._announce(
                "puppet_ndi_failed",
                "NDI unavailable (install ndi-python + the NDI Runtime).",
            )
            return
        if enabled:
            self._announce(
                "puppet_ndi_on",
                'NDI source "{name}" broadcasting — add an "NDI Source" '
                "in OBS (requires the obs-ndi plugin).",
                name=self._ndi_output.source_name(),
            )
        else:
            self._announce("puppet_ndi_off", "NDI stopped")

    def _toggle_vts_api(self, enabled: bool) -> None:
        ok = self._vts_server.set_enabled(enabled)
        if enabled and not ok:
            self._vts_toggle.blockSignals(True)
            self._vts_toggle.setChecked(False)
            self._vts_toggle.blockSignals(False)
            self._announce(
                "puppet_vts_unavailable",
                "VTS API unavailable (install PySide6 with QtWebSockets)",
            )
            return
        self._announce(
            "puppet_vts_on" if enabled else "puppet_vts_off",
            "VTS API listening on 127.0.0.1:{port}"
            if enabled else "VTS API stopped",
        )
