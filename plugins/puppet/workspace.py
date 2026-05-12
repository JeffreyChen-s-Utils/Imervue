"""Top-level Puppet workspace — QMainWindow that hosts the canvas,
toolbar, recent files, parameter dock, and (future) timeline /
expression / physics docks.

Recent puppet paths are persisted to
``user_setting_dict["puppet_recent_files"]`` so they survive across
launches; missing files are pruned silently the next time the menu is
rebuilt (matches the recent-folder behaviour in
``Imervue/menu/recent_menu.py``).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStatusBar,
    QToolBar,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict
from puppet.auto_mesh import DEFAULT_CELL_SIZE, puppet_from_png
from puppet.canvas import PuppetCanvas
from puppet.document_io import PuppetFormatError, load_puppet, save_puppet
from puppet.operations import (
    add_parameter,
    add_rotation_deformer,
    add_warp_deformer,
    remove_key,
    set_key_at_value,
    snapshot_current_forms,
)
from puppet.cubism_import import (
    CubismFormatError,
    apply_bundle,
    load_cdi3,
    load_exp3,
    load_model3,
    load_motion3,
    load_physics3,
    load_pose3,
)
from puppet.expression_dock import ExpressionDock
from puppet.idle_driver import IdleDriver
from puppet.idle_motion_cycler import IdleMotionCycler
from puppet.psd_import import puppet_from_psd
from puppet.requirements import (
    LIPSYNC_PACKAGES,
    WEBCAM_PACKAGES,
    all_optional_packages,
    missing_packages,
)
from puppet.vts_api import VTubeStudioServer
from puppet.input_engine import InputEngine
from puppet.motion_dock import MotionDock
from puppet.motion_recorder import MotionRecorder, append_motion
from puppet.motion_timeline import MotionTimelineDialog
from puppet.parameter_dock import ParameterDock
from puppet.recorder import RecordingSession, save_canvas_png
from puppet.webcam_tracker import WebcamTracker

logger = logging.getLogger("Imervue.plugin.puppet.workspace")

_RECENT_KEY = "puppet_recent_files"
_RECENT_LIMIT = 10


class PuppetWorkspace(QMainWindow):
    """Top-level QMainWindow hosted by the Puppet plugin tab.

    Inherits from QMainWindow so QToolBar / QDockWidget / QStatusBar
    plug in via the standard Qt APIs (matches the pattern used by
    ``Imervue/paint/paint_workspace.py``).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # The window flag keeps QMainWindow from being treated as a
        # real top-level window when embedded in a tab.
        self.setWindowFlags(Qt.WindowType.Widget)

        self._canvas = PuppetCanvas(self)
        self.setCentralWidget(self._canvas)

        self.addToolBar(self._build_toolbar())

        self._parameter_dock = ParameterDock(self._canvas, self, workspace=self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._parameter_dock,
        )

        self._expression_dock = ExpressionDock(self._canvas, self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._expression_dock,
        )
        # Tabify so the user gets Parameters/Expressions as two tabs in
        # the same right pane instead of a cramped split. Parameters is
        # the more-frequently-used one so it stays on top.
        self.tabifyDockWidget(self._expression_dock, self._parameter_dock)

        self._motion_dock = MotionDock(self._canvas, self)
        # Live2D-style transition feel: when the user switches motions
        # we ease across 0.5s rather than snap. Per-motion fade fields
        # (e.g. from a Cubism .motion3.json import) override this.
        self._motion_dock.player().set_default_fade(0.5, 0.5)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._motion_dock,
        )

        self._input_engine = InputEngine(self._canvas, self)
        self._idle_driver = IdleDriver(self._canvas, self)
        self._idle_motion_cycler = IdleMotionCycler(
            self._motion_dock.player(), self._canvas, self,
        )
        self._vts_server = VTubeStudioServer(self._canvas, self)
        self._recorder = RecordingSession(self._canvas, self)
        self._recorder.finished.connect(self._on_recording_finished)
        self._recorder.failed.connect(self._on_recording_failed)
        self._webcam = WebcamTracker(self._canvas, self)
        self._motion_recorder = MotionRecorder(self._canvas, self)
        self._motion_recorder.finished.connect(self._on_motion_recorded)
        self._canvas.hit_area_triggered.connect(self._on_hit_area_triggered)

        self._status_label = QLabel("")
        bar = QStatusBar()
        bar.addWidget(self._status_label, stretch=1)
        self.setStatusBar(bar)
        self._refresh_status_for_no_document()

    def canvas(self) -> PuppetCanvas:
        return self._canvas

    def parameter_dock(self) -> ParameterDock:
        return self._parameter_dock

    def expression_dock(self) -> ExpressionDock:
        return self._expression_dock

    def idle_driver(self) -> IdleDriver:
        return self._idle_driver

    # ---- toolbar --------------------------------------------------------

    def _build_toolbar(self) -> QToolBar:
        lang = language_wrapper.language_word_dict
        bar = QToolBar(lang.get("puppet_toolbar_title", "Puppet"), self)
        bar.setMovable(False)

        open_action = QAction(lang.get("puppet_open", "Open Puppet…"), self)
        open_action.triggered.connect(self._open_via_dialog)
        bar.addAction(open_action)

        import_action = QAction(lang.get("puppet_import_png", "Import PNG…"), self)
        import_action.triggered.connect(self._import_png_via_dialog)
        bar.addAction(import_action)

        import_psd_action = QAction(
            lang.get("puppet_import_psd", "Import PSD…"), self,
        )
        import_psd_action.triggered.connect(self._import_psd_via_dialog)
        bar.addAction(import_psd_action)

        import_cubism_action = QAction(
            lang.get("puppet_import_cubism", "Import Cubism…"), self,
        )
        import_cubism_action.triggered.connect(self._import_cubism_via_dialog)
        bar.addAction(import_cubism_action)

        install_deps_action = QAction(
            lang.get("puppet_install_deps", "Install dependencies…"), self,
        )
        install_deps_action.triggered.connect(self._install_all_optional_deps)
        bar.addAction(install_deps_action)

        self._recent_button = QPushButton(lang.get("puppet_recent", "Recent"))
        self._recent_button.setFlat(True)
        self._recent_menu = QMenu(self._recent_button)
        self._recent_button.setMenu(self._recent_menu)
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        bar.addWidget(self._recent_button)

        bar.addSeparator()

        save_action = QAction(lang.get("puppet_save_as", "Save As…"), self)
        save_action.triggered.connect(self._save_via_dialog)
        bar.addAction(save_action)

        bar.addSeparator()

        add_rot_action = QAction(
            lang.get("puppet_add_rotation", "Add Rotation Deformer"), self,
        )
        add_rot_action.triggered.connect(self._add_rotation_deformer)
        bar.addAction(add_rot_action)

        add_warp_action = QAction(
            lang.get("puppet_add_warp", "Add Warp Deformer"), self,
        )
        add_warp_action.triggered.connect(self._add_warp_deformer)
        bar.addAction(add_warp_action)

        add_param_action = QAction(
            lang.get("puppet_add_parameter", "Add Parameter"), self,
        )
        add_param_action.triggered.connect(self._add_parameter)
        bar.addAction(add_param_action)

        bar.addSeparator()

        self._drag_toggle = QAction(
            lang.get("puppet_drag_track", "Drag-track head"), self,
        )
        self._drag_toggle.setCheckable(True)
        self._drag_toggle.toggled.connect(self._toggle_drag)
        bar.addAction(self._drag_toggle)

        self._blink_toggle = QAction(
            lang.get("puppet_auto_blink", "Auto-blink"), self,
        )
        self._blink_toggle.setCheckable(True)
        self._blink_toggle.toggled.connect(self._toggle_blink)
        bar.addAction(self._blink_toggle)

        self._lipsync_toggle = QAction(
            lang.get("puppet_lipsync", "Mic lip-sync"), self,
        )
        self._lipsync_toggle.setCheckable(True)
        self._lipsync_toggle.toggled.connect(self._toggle_lipsync)
        bar.addAction(self._lipsync_toggle)

        self._webcam_toggle = QAction(
            lang.get("puppet_webcam", "Webcam tracking"), self,
        )
        self._webcam_toggle.setCheckable(True)
        self._webcam_toggle.toggled.connect(self._toggle_webcam)
        bar.addAction(self._webcam_toggle)

        self._idle_toggle = QAction(
            lang.get("puppet_auto_idle", "Auto idle"), self,
        )
        self._idle_toggle.setCheckable(True)
        self._idle_toggle.toggled.connect(self._toggle_idle)
        bar.addAction(self._idle_toggle)

        self._idle_motion_toggle = QAction(
            lang.get("puppet_idle_motions", "Idle motions"), self,
        )
        self._idle_motion_toggle.setCheckable(True)
        self._idle_motion_toggle.toggled.connect(self._toggle_idle_motions)
        bar.addAction(self._idle_motion_toggle)

        self._vts_toggle = QAction(
            lang.get("puppet_vts_api", "VTS API"), self,
        )
        self._vts_toggle.setCheckable(True)
        self._vts_toggle.toggled.connect(self._toggle_vts_api)
        bar.addAction(self._vts_toggle)

        bar.addSeparator()

        self._mesh_edit_toggle = QAction(
            lang.get("puppet_mesh_edit", "Edit mesh"), self,
        )
        self._mesh_edit_toggle.setCheckable(True)
        self._mesh_edit_toggle.toggled.connect(self._toggle_mesh_edit)
        bar.addAction(self._mesh_edit_toggle)

        self._motion_record_toggle = QAction(
            lang.get("puppet_record_motion", "Record motion"), self,
        )
        self._motion_record_toggle.setCheckable(True)
        self._motion_record_toggle.toggled.connect(self._toggle_motion_record)
        bar.addAction(self._motion_record_toggle)

        edit_motion_action = QAction(
            lang.get("puppet_edit_motion", "Edit motion…"), self,
        )
        edit_motion_action.triggered.connect(self._edit_active_motion)
        bar.addAction(edit_motion_action)

        bar.addSeparator()

        capture_action = QAction(lang.get("puppet_capture", "Capture frame…"), self)
        capture_action.triggered.connect(self._capture_via_dialog)
        bar.addAction(capture_action)

        self._record_action = QAction(lang.get("puppet_record", "Record…"), self)
        self._record_action.setCheckable(True)
        self._record_action.toggled.connect(self._toggle_recording)
        bar.addAction(self._record_action)

        bar.addSeparator()

        fit_action = QAction(lang.get("puppet_fit_view", "Fit to Window"), self)
        fit_action.triggered.connect(self._canvas_reset_view)
        bar.addAction(fit_action)

        return bar

    # ---- file ops -------------------------------------------------------

    def _open_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_open_dialog_title", "Open Puppet"),
            "",
            "Puppet (*.puppet)",
        )
        if not path:
            return
        self.open_puppet(path)

    def open_puppet(self, path: str | Path) -> bool:
        """Load ``path`` into the canvas. Returns ``True`` on success."""
        path_str = str(path)
        try:
            doc = load_puppet(path_str)
        except (FileNotFoundError, PuppetFormatError) as exc:
            logger.warning("failed to open puppet %s: %s", path_str, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_open_failed", "Failed to open puppet: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_loaded",
                "Loaded {name} ({w}×{h}, {n} drawables)",
            ).format(
                name=Path(path_str).name,
                w=doc.size[0], h=doc.size[1],
                n=len(doc.drawables),
            ),
        )
        _push_recent(path_str)
        return True

    def _canvas_reset_view(self) -> None:
        self._canvas.reset_view()

    # ---- save -----------------------------------------------------------

    def _save_via_dialog(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("puppet_save_dialog_title", "Save Puppet As"),
            "",
            "Puppet (*.puppet)",
        )
        if not path:
            return
        if not path.lower().endswith(".puppet"):
            path = f"{path}.puppet"
        self.save_puppet(path)

    def save_puppet(self, path: str | Path) -> bool:
        doc = self._canvas.document()
        if doc is None:
            return False
        try:
            save_puppet(doc, path)
        except OSError as exc:
            logger.warning("puppet save failed: %s", exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_save_failed", "Save failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_save_done", "Saved to {name}",
            ).format(name=Path(str(path)).name),
        )
        _push_recent(str(path))
        return True

    # ---- editor authoring ----------------------------------------------

    def _add_rotation_deformer(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        deformer_id = self._unique_deformer_id("rotation")
        if add_rotation_deformer(doc, deformer_id):
            self._canvas.load_document(doc)
            self._announce(
                "puppet_added_deformer", "Added deformer {id}",
                id=deformer_id,
            )

    def _add_warp_deformer(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        deformer_id = self._unique_deformer_id("warp")
        if add_warp_deformer(doc, deformer_id):
            self._canvas.load_document(doc)
            self._announce(
                "puppet_added_deformer", "Added deformer {id}",
                id=deformer_id,
            )

    def _add_parameter(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            return
        param_id = self._unique_parameter_id("Param")
        if add_parameter(doc, param_id):
            # Force the dock to rebuild itself by replaying load_document
            self._canvas.load_document(doc)
            self._announce(
                "puppet_added_parameter", "Added parameter {id}",
                id=param_id,
            )

    def set_key_at_current_slider(self, param_id: str) -> bool:
        """Snapshot current deformer forms at the slider's current
        value and write them as a key on ``param_id``. Wired by the
        parameter dock's per-row Set Key button."""
        doc = self._canvas.document()
        if doc is None:
            return False
        value = self._canvas.parameter_values().get(param_id)
        if value is None:
            return False
        forms = snapshot_current_forms(doc)
        ok = set_key_at_value(doc, param_id, value, forms)
        if ok:
            self._announce(
                "puppet_key_set", "Set key on {id} at {value:.2f}",
                id=param_id, value=value,
            )
        return ok

    def remove_key_at_current_slider(self, param_id: str) -> bool:
        doc = self._canvas.document()
        if doc is None:
            return False
        value = self._canvas.parameter_values().get(param_id)
        if value is None:
            return False
        ok = remove_key(doc, param_id, value)
        if ok:
            self._canvas.load_document(doc)   # re-evaluate at neutral keys
            self._canvas.set_parameter_value(param_id, value)
            self._announce(
                "puppet_key_removed", "Removed key from {id} at {value:.2f}",
                id=param_id, value=value,
            )
        return ok

    # ---- helpers --------------------------------------------------------

    def _unique_deformer_id(self, prefix: str) -> str:
        doc = self._canvas.document()
        existing = {d.id for d in (doc.deformers if doc else [])}
        i = 1
        while True:
            candidate = f"{prefix}_{i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _unique_parameter_id(self, prefix: str) -> str:
        doc = self._canvas.document()
        existing = {p.id for p in (doc.parameters if doc else [])}
        i = 1
        while True:
            candidate = f"{prefix}{i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _announce(self, key: str, fallback: str, **fmt) -> None:
        self._status_label.setText(
            language_wrapper.language_word_dict.get(key, fallback).format(**fmt),
        )

    # ---- live input toggles --------------------------------------------

    def _toggle_drag(self, enabled: bool) -> None:
        self._input_engine.set_drag_enabled(enabled)

    def _toggle_blink(self, enabled: bool) -> None:
        self._input_engine.set_blink_enabled(enabled)

    def _toggle_lipsync(self, enabled: bool) -> None:
        if enabled and missing_packages(LIPSYNC_PACKAGES):
            self._prompt_install(
                LIPSYNC_PACKAGES,
                on_ready=lambda: self._lipsync_toggle.setChecked(True),
            )
            self._reset_toggle(self._lipsync_toggle)
            return
        ok = self._input_engine.set_lipsync_enabled(enabled)
        if enabled and not ok:
            # sounddevice is importable but mic open failed (no device,
            # permission denied …) — bounce the toggle with the
            # existing diagnostic so the user knows the install isn't
            # the issue.
            self._reset_toggle(self._lipsync_toggle)
            self._announce(
                "puppet_lipsync_unavailable",
                "Lip-sync unavailable (install sounddevice for mic input)",
            )

    def input_engine(self) -> InputEngine:
        return self._input_engine

    # ---- optional-dep install --------------------------------------

    def _prompt_install(
        self,
        packages: list[tuple[str, str]],
        *,
        on_ready=None,
    ) -> None:
        """Open the main app's pip-installer dialog for ``packages``.
        Imported lazily so test environments without the full Imervue
        UI stack can still construct the workspace."""
        from Imervue.plugin.pip_installer import ensure_dependencies
        ensure_dependencies(self, packages, on_ready or (lambda: None))

    def _reset_toggle(self, action: QAction) -> None:
        """Bounce a checkable QAction back to off without re-firing the
        ``toggled`` signal — used when a toggle's prerequisite fails."""
        action.blockSignals(True)
        action.setChecked(False)
        action.blockSignals(False)

    def _install_all_optional_deps(self) -> None:
        """Toolbar action — install every optional puppet dependency
        in one batch so the user can prepare a machine for offline use
        without exercising each feature individually."""
        packages = all_optional_packages()
        missing = missing_packages(packages)
        if not missing:
            self._announce(
                "puppet_deps_already_installed",
                "All optional puppet dependencies are already installed.",
            )
            return
        self._prompt_install(packages, on_ready=lambda: self._announce(
            "puppet_deps_installed",
            "Optional puppet dependencies installed.",
        ))

    # ---- capture / record ----------------------------------------------

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
        ok = save_canvas_png(self._canvas, path)
        if ok:
            self._announce(
                "puppet_capture_saved", "Saved frame to {name}",
                name=Path(path).name,
            )
        else:
            self._announce(
                "puppet_capture_failed",
                "Capture failed (canvas not yet rendered)",
            )

    def _toggle_recording(self, enabled: bool) -> None:
        if enabled:
            self._start_recording()
        else:
            self._recorder.stop()

    def _start_recording(self) -> None:
        if self._canvas.document() is None:
            self._record_action.setChecked(False)
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang.get("puppet_record_dialog_title", "Record Animation"),
            "",
            "GIF (*.gif);;WebM (*.webm);;MP4 (*.mp4)",
        )
        if not path:
            self._record_action.setChecked(False)
            return
        ok = self._recorder.start(path)
        if not ok:
            self._record_action.setChecked(False)

    def _on_recording_finished(self, path: str) -> None:
        self._announce(
            "puppet_record_saved", "Recording saved to {name}",
            name=Path(path).name,
        )
        self._record_action.blockSignals(True)
        self._record_action.setChecked(False)
        self._record_action.blockSignals(False)

    def _on_recording_failed(self, reason: str) -> None:
        self._announce(
            "puppet_record_failed", "Recording failed: {error}",
            error=reason,
        )
        self._record_action.blockSignals(True)
        self._record_action.setChecked(False)
        self._record_action.blockSignals(False)

    # ---- webcam tracking ----------------------------------------------

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
        ok = self._webcam.set_enabled(enabled)
        if enabled and not ok:
            self._reset_toggle(self._webcam_toggle)
            self._announce(
                "puppet_webcam_unavailable",
                "Webcam tracking unavailable (install opencv-python + mediapipe)",
            )

    # ---- idle driver ---------------------------------------------------

    def _toggle_idle(self, enabled: bool) -> None:
        self._idle_driver.set_enabled(enabled)
        self._announce(
            "puppet_idle_on" if enabled else "puppet_idle_off",
            "Auto idle on" if enabled else "Auto idle off",
        )

    def _toggle_idle_motions(self, enabled: bool) -> None:
        """Toggle the Idle motion cycler. Independent of ``_toggle_idle``:
        the breath/drift driver runs at parameter level, the cycler at
        motion level — both can be enabled together for the fullest
        Live2D-style "alive" feel."""
        self._idle_motion_cycler.set_enabled(enabled)
        self._announce(
            "puppet_idle_motions_on" if enabled else "puppet_idle_motions_off",
            "Idle motions on" if enabled else "Idle motions off",
        )

    def idle_motion_cycler(self) -> IdleMotionCycler:
        return self._idle_motion_cycler

    # ---- VTube Studio API ---------------------------------------------

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

    # ---- mesh-edit toggle ---------------------------------------------

    def _toggle_mesh_edit(self, enabled: bool) -> None:
        self._canvas.set_mesh_edit_enabled(enabled)
        self._announce(
            "puppet_mesh_edit_on" if enabled else "puppet_mesh_edit_off",
            "Mesh editing on" if enabled else "Mesh editing off",
        )

    # ---- motion timeline editor ---------------------------------------

    def _edit_active_motion(self) -> None:
        player = self._motion_dock.player()
        motion = player.motion()
        if motion is None:
            self._announce(
                "puppet_no_active_motion",
                "Pick a motion from the dock before editing.",
            )
            return
        dialog = MotionTimelineDialog(motion, self)
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

    # ---- motion recording ---------------------------------------------

    def _toggle_motion_record(self, enabled: bool) -> None:
        if enabled:
            if not self._start_motion_recording():
                self._motion_record_toggle.blockSignals(True)
                self._motion_record_toggle.setChecked(False)
                self._motion_record_toggle.blockSignals(False)
        else:
            self._motion_recorder.stop()

    def _start_motion_recording(self) -> bool:
        if self._canvas.document() is None:
            return False
        from PySide6.QtWidgets import QInputDialog
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("puppet_record_motion_title", "Record motion"),
            lang.get("puppet_record_motion_prompt", "Motion name:"),
            text="user_motion",
        )
        if not ok or not name.strip():
            return False
        return self._motion_recorder.start(name.strip())

    # ---- hit areas ------------------------------------------------------

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
            else:
                self._motion_dock.select_motion(area.motion)
        if area.expression:
            if area.expression in self._canvas.active_expressions():
                self._canvas.remove_expression(area.expression)
            else:
                self._canvas.add_expression(area.expression)
        self._announce(
            "puppet_hit_area_triggered", "Hit area '{id}' triggered",
            id=area_id,
        )

    def _on_motion_recorded(self, motion) -> None:
        if motion is None:
            return
        if append_motion(self._canvas, motion):
            self._announce(
                "puppet_motion_recorded",
                "Recorded motion '{name}' ({duration:.1f}s, {tracks} tracks)",
                name=motion.name,
                duration=motion.duration,
                tracks=len(motion.tracks),
            )

    # ---- import PNG -----------------------------------------------------

    def _import_png_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_import_png_title", "Import PNG"),
            "",
            "PNG (*.png);;Images (*.png *.jpg *.jpeg *.bmp *.tiff)",
        )
        if not path:
            return
        cell_size = self._prompt_cell_size()
        if cell_size is None:
            return
        self.import_png(path, cell_size=cell_size)

    def _prompt_cell_size(self) -> int | None:
        lang = language_wrapper.language_word_dict
        value, ok = QInputDialog.getInt(
            self,
            lang.get("puppet_cell_size_title", "Mesh density"),
            lang.get(
                "puppet_cell_size_prompt",
                "Cell size in pixels (smaller = denser mesh):",
            ),
            DEFAULT_CELL_SIZE, 4, 1024, 4,
        )
        return value if ok else None

    # ---- import PSD -----------------------------------------------------

    def _import_psd_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_import_psd_title", "Import PSD"),
            "",
            "PSD (*.psd)",
        )
        if not path:
            return
        self.import_psd(path)

    def import_psd(self, path: str | Path) -> bool:
        """Load ``path`` (a PSD) as a multi-drawable puppet. Returns
        ``True`` on success."""
        try:
            doc = puppet_from_psd(path)
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning("PSD import failed for %s: %s", path, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_psd_import_failed",
                    "PSD import failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_psd_imported",
                "Imported {name} ({w}×{h}, {n} drawables)",
            ).format(
                name=Path(str(path)).name,
                w=doc.size[0], h=doc.size[1],
                n=len(doc.drawables),
            ),
        )
        return True

    # ---- import Cubism ------------------------------------------------

    def _import_cubism_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_import_cubism_title", "Import Cubism file"),
            "",
            "Cubism (*.model3.json *.motion3.json *.exp3.json "
            "*.physics3.json *.pose3.json *.cdi3.json)",
        )
        if not path:
            return
        self.import_cubism(path)

    def import_cubism(self, path: str | Path) -> bool:
        """Route by filename suffix: ``.model3.json`` loads the bundle
        and merges everything; ``.motion3.json`` and ``.exp3.json``
        append a single motion or expression. The active document is
        required — there's no rig to attach the imported assets to
        without one. Returns ``True`` on success."""
        doc = self._canvas.document()
        if doc is None:
            self._announce(
                "puppet_cubism_no_document",
                "Open or import a puppet first before adding Cubism assets.",
            )
            return False
        path_str = str(path)
        try:
            self._dispatch_cubism_import(doc, path_str)
        except (FileNotFoundError, CubismFormatError, OSError) as exc:
            logger.warning("Cubism import failed for %s: %s", path_str, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_cubism_failed", "Cubism import failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        self._announce(
            "puppet_cubism_imported", "Imported Cubism asset {name}",
            name=Path(path_str).name,
        )
        return True

    def _dispatch_cubism_import(self, doc, path_str: str) -> None:
        lower = path_str.lower()
        if lower.endswith(".model3.json"):
            apply_bundle(doc, load_model3(path_str))
        elif lower.endswith(".motion3.json"):
            doc.motions.append(load_motion3(path_str))
        elif lower.endswith(".exp3.json"):
            doc.expressions.append(load_exp3(path_str))
        elif lower.endswith(".physics3.json"):
            doc.physics_rigs.extend(load_physics3(path_str))
        elif lower.endswith(".pose3.json"):
            doc.pose_groups.extend(load_pose3(path_str))
        elif lower.endswith(".cdi3.json"):
            doc.display_names.update(load_cdi3(path_str))
        else:
            raise CubismFormatError(
                f"unrecognised Cubism file extension on {path_str}",
            )

    def import_png(self, path: str | Path, *, cell_size: int = DEFAULT_CELL_SIZE) -> bool:
        """Build a single-drawable puppet from ``path``'s PNG and load
        it into the canvas. Returns ``True`` on success."""
        try:
            doc = puppet_from_png(path, cell_size=cell_size)
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning("PNG import failed for %s: %s", path, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_import_failed",
                    "PNG import failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        n_verts = len(doc.drawables[0].vertices)
        n_tris = len(doc.drawables[0].indices) // 3
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_imported",
                "Imported {name} ({w}×{h}, {v} vertices, {t} triangles)",
            ).format(
                name=Path(str(path)).name,
                w=doc.size[0], h=doc.size[1],
                v=n_verts, t=n_tris,
            ),
        )
        return True

    # ---- recent menu ----------------------------------------------------

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        lang = language_wrapper.language_word_dict
        valid: list[str] = []
        for path in user_setting_dict.get(_RECENT_KEY, []):
            if Path(path).is_file():
                valid.append(path)
                action = self._recent_menu.addAction(Path(path).name)
                action.setToolTip(path)
                action.triggered.connect(
                    lambda _checked=False, p=path: self.open_puppet(p),
                )
        user_setting_dict[_RECENT_KEY] = valid
        if not valid:
            empty = self._recent_menu.addAction(
                lang.get("puppet_recent_empty", "(No recent puppets)"),
            )
            empty.setEnabled(False)

    # ---- status ---------------------------------------------------------

    def _refresh_status_for_no_document(self) -> None:
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_empty",
                "No puppet loaded — use Open to load a .puppet file.",
            ),
        )

    # ---- compatibility shim for older tests / callers -------------------
    # Phase 0–3 tests reach into ``_status`` for status-text assertions;
    # the QMainWindow now exposes that through the QStatusBar's label.
    @property
    def _status(self) -> QLabel:
        return self._status_label


def _push_recent(path: str) -> None:
    """Move ``path`` to the front of the recent-files list, dedupe,
    truncate to ``_RECENT_LIMIT``."""
    existing = [p for p in user_setting_dict.get(_RECENT_KEY, []) if p != path]
    existing.insert(0, path)
    user_setting_dict[_RECENT_KEY] = existing[:_RECENT_LIMIT]
