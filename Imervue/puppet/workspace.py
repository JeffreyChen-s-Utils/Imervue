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
    QStatusBar,
)

from Imervue.gui.file_filters import translated_filter
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.document_io import PuppetFormatError, load_puppet, save_puppet
from Imervue.puppet.operations import (
    add_parameter,
    add_rotation_deformer,
    add_warp_deformer,
    remove_key,
    set_key_at_value,
    snapshot_current_forms,
)
from Imervue.puppet.expression_dock import ExpressionDock
from Imervue.puppet.idle_driver import IdleDriver
from Imervue.puppet.idle_motion_cycler import IdleMotionCycler
from Imervue.puppet.batch_export import BatchMotionExporter, SUPPORTED_EXTENSIONS
from Imervue.puppet.bone_tree_dock import BoneTreeDock
from Imervue.puppet.ndi_output import NDIOutput
from Imervue.puppet.requirements import (
    LIPSYNC_PACKAGES,
    all_optional_packages,
    missing_packages,
)
from Imervue.puppet.symmetrize import auto_mirror_pair, mirror_id
from Imervue.puppet.validator import severity_counts, validate
from Imervue.puppet.virtual_camera import VirtualCameraOutput
from Imervue.puppet.vts_api import VTubeStudioServer
from Imervue.puppet.input_engine import InputEngine
from Imervue.puppet.motion_dock import MotionDock
from Imervue.puppet.motion_recorder import MotionRecorder, append_motion
from Imervue.puppet.motion_timeline import MotionTimelineDialog
from Imervue.puppet.parameter_dock import ParameterDock
from Imervue.puppet.recorder import RecordingSession
from Imervue.puppet.webcam_tracker import WebcamTracker
from Imervue.puppet.workspace_import import PuppetImportMixin
from Imervue.puppet.workspace_live import PuppetLiveMixin
from Imervue.puppet.workspace_menus import RECENT_KEY, PuppetMenusMixin
from Imervue.system.best_effort import best_effort

logger = logging.getLogger("Imervue.plugin.puppet.workspace")

_RECENT_LIMIT = 10





class PuppetWorkspace(PuppetMenusMixin, PuppetLiveMixin, PuppetImportMixin, QMainWindow):
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

        # Build the actions first; menu and toolbar both reference the
        # same QAction objects so toggling one updates the other.
        self._build_actions()
        self.setMenuBar(self._build_menu_bar())
        self.addToolBar(
            Qt.ToolBarArea.TopToolBarArea, self._build_toggle_toolbar(),
        )

        self._build_docks()
        self._build_controllers()
        self._build_status_bar()
        self._refresh_status_for_no_document()

    def _build_docks(self) -> None:
        """Parameters / Expressions / Bones tabbed on the right, Motions at the bottom."""
        self._parameter_dock = ParameterDock(self._canvas, self, workspace=self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._parameter_dock,
        )

        self._expression_dock = ExpressionDock(self._canvas, self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._expression_dock,
        )
        self._bone_tree_dock = BoneTreeDock(self._canvas, self)
        self._bone_tree_dock.hierarchy_changed.connect(
            self._on_bone_hierarchy_changed,
        )
        self._bone_tree_dock.deformer_selected.connect(
            self._canvas.set_selected_deformer,
        )
        # Right-click on canvas clears overlay → tree-row deselects in
        # lockstep so the user can't end up with one side highlighted
        # and the other not.
        self._canvas.selection_cleared.connect(
            self._bone_tree_dock.clear_selection,
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._bone_tree_dock,
        )
        # Tabify so the user gets Parameters/Expressions/Bones as
        # three tabs in the same right pane instead of a cramped split.
        # Parameters is the most-frequent one so it stays on top.
        self.tabifyDockWidget(self._expression_dock, self._parameter_dock)
        self.tabifyDockWidget(self._expression_dock, self._bone_tree_dock)

        self._motion_dock = MotionDock(self._canvas, self)
        # Live2D-style transition feel: when the user switches motions
        # we ease across 0.5s rather than snap. Per-motion fade fields
        # (e.g. from a Cubism .motion3.json import) override this.
        self._motion_dock.player().set_default_fade(0.5, 0.5)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._motion_dock,
        )

    def _build_controllers(self) -> None:
        """Input, idle, streaming, export and recording controllers bound to the canvas."""
        self._input_engine = InputEngine(self._canvas, self)
        self._idle_driver = IdleDriver(self._canvas, self)
        self._idle_motion_cycler = IdleMotionCycler(
            self._motion_dock.player(), self._canvas, self,
        )
        self._vts_server = VTubeStudioServer(self._canvas, self)
        self._virtual_camera = VirtualCameraOutput(self._canvas, self)
        self._ndi_output = NDIOutput(self._canvas, self)
        self._batch_exporter = BatchMotionExporter(
            self._canvas, self._motion_dock.player(), self,
        )
        self._batch_exporter.progress.connect(self._on_batch_progress)
        self._batch_exporter.finished.connect(self._on_batch_finished)
        self._batch_exporter.failed.connect(self._on_batch_failed)
        self._recorder = RecordingSession(self._canvas, self)
        self._recorder.finished.connect(self._on_recording_finished)
        self._recorder.failed.connect(self._on_recording_failed)
        self._webcam = WebcamTracker(self._canvas, self)
        self._motion_recorder = MotionRecorder(self._canvas, self)
        self._motion_recorder.finished.connect(self._on_motion_recorded)
        self._canvas.hit_area_triggered.connect(self._on_hit_area_triggered)

    def _build_status_bar(self) -> None:
        """Status bar with the stretching message label."""
        self._status_label = QLabel("")
        bar = QStatusBar()
        bar.addWidget(self._status_label, stretch=1)
        self.setStatusBar(bar)

    def canvas(self) -> PuppetCanvas:
        return self._canvas

    def parameter_dock(self) -> ParameterDock:
        return self._parameter_dock

    def expression_dock(self) -> ExpressionDock:
        return self._expression_dock

    def idle_driver(self) -> IdleDriver:
        return self._idle_driver

    # ---- menu bar + toolbar -------------------------------------------

    # ---- file ops -------------------------------------------------------

    def _open_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_open_dialog_title", "Open Puppet"),
            "",
            translated_filter("file_filter_puppet", "Puppet files", ("puppet",)),
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

    # ---- reset-to-rest --------------------------------------------------

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
        # 4. Snap parameters back to their authored defaults.
        self._canvas.reset_parameters()
        # 5. Status feedback so the user sees the action took effect.
        lang = language_wrapper.language_word_dict
        self._status.setText(
            lang.get("puppet_status_reset", "Rig reset to neutral pose."),
        )

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
            translated_filter("file_filter_puppet", "Puppet files", ("puppet",)),
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

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        self._shutdown_drivers()
        super().closeEvent(event)

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

    # ---- webcam tracking ----------------------------------------------

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

    # ---- bone tree -----------------------------------------------------

    def _on_bone_hierarchy_changed(self) -> None:
        """Re-render the canvas after a reparent so the new FK order
        is reflected on screen without a manual reload."""
        doc = self._canvas.document()
        if doc is not None:
            self._canvas.load_document(doc)

    # ---- validator -----------------------------------------------------

    def _run_validator(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            self._announce(
                "puppet_validate_no_doc",
                "Load a puppet first before validating.",
            )
            return
        issues = validate(doc)
        counts = severity_counts(issues)
        if not issues:
            self._announce(
                "puppet_validate_clean",
                "Validation clean — no issues found.",
            )
            return
        self._show_validator_dialog(issues, counts)

    def _show_validator_dialog(self, issues, counts) -> None:
        from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout
        lang = language_wrapper.language_word_dict
        dialog = QDialog(self)
        dialog.setWindowTitle(
            lang.get("puppet_validate_title", "Validation report"),
        )
        dialog.resize(720, 480)
        layout = QVBoxLayout(dialog)
        summary = QLabel(
            lang.get(
                "puppet_validate_summary",
                "{errors} errors, {warnings} warnings, {info} info",
            ).format(
                errors=counts.get("error", 0),
                warnings=counts.get("warning", 0),
                info=counts.get("info", 0),
            ),
        )
        layout.addWidget(summary)
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setPlainText("\n".join(
            f"[{issue.severity.upper()}] {issue.code}  {issue.location}\n  {issue.message}"
            for issue in issues
        ))
        layout.addWidget(body)
        dialog.exec()

    # ---- mirror drawable ----------------------------------------------

    def _mirror_drawable_via_dialog(self) -> None:
        doc = self._canvas.document()
        if doc is None or not doc.drawables:
            self._announce(
                "puppet_mirror_no_drawables",
                "Load a puppet with drawables first.",
            )
            return
        lang = language_wrapper.language_word_dict
        names = [d.id for d in doc.drawables]
        source, ok = QInputDialog.getItem(
            self,
            lang.get("puppet_mirror_title", "Mirror drawable"),
            lang.get("puppet_mirror_prompt", "Source drawable:"),
            names, 0, False,
        )
        if not ok or not source:
            return
        suggested = mirror_id(source)
        target, ok = QInputDialog.getText(
            self,
            lang.get("puppet_mirror_title", "Mirror drawable"),
            lang.get("puppet_mirror_target", "Mirrored id:"),
            text=suggested,
        )
        if not ok or not target.strip():
            return
        created = auto_mirror_pair(doc, source, new_id=target.strip())
        if created is None:
            self._announce(
                "puppet_mirror_failed",
                "Mirror failed — id {target!r} already exists.",
                target=target,
            )
            return
        self._canvas.load_document(doc)
        self._announce(
            "puppet_mirror_done",
            "Mirrored {source} → {target}.",
            source=source, target=created.id,
        )

    # ---- batch export -------------------------------------------------

    def _batch_export_via_dialog(self) -> None:
        doc = self._canvas.document()
        if doc is None or not doc.motions:
            self._announce(
                "puppet_batch_no_motions",
                "Document has no motions to export.",
            )
            return
        lang = language_wrapper.language_word_dict
        directory = QFileDialog.getExistingDirectory(
            self,
            lang.get("puppet_batch_dir_title", "Export motions to…"),
            "",
        )
        if not directory:
            return
        # Format pick — use a simple input dialog rather than a custom
        # dialog so the workspace stays small. Defaults to MP4.
        ext_choices = list(SUPPORTED_EXTENSIONS)
        ext, ok = QInputDialog.getItem(
            self,
            lang.get("puppet_batch_format_title", "Output format"),
            lang.get("puppet_batch_format_prompt", "Container:"),
            ext_choices, 0, False,
        )
        if not ok:
            return
        self._batch_exporter.start(directory, extension=ext)

    def _on_batch_progress(self, index: int, total: int, name: str) -> None:
        self._announce(
            "puppet_batch_progress",
            "Exporting motion {index}/{total}: {name}",
            index=index + 1, total=total, name=name,
        )

    def _on_batch_finished(self, paths: list) -> None:
        self._announce(
            "puppet_batch_done",
            "Exported {count} motions.",
            count=len(paths),
        )

    def _on_batch_failed(self, reason: str) -> None:
        self._announce(
            "puppet_batch_failed", "Batch export failed: {error}",
            error=reason,
        )

    # ---- virtual camera ------------------------------------------------

    # ---- NDI output ----------------------------------------------------

    # ---- VTube Studio API ---------------------------------------------

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

    # ---- import PSD -----------------------------------------------------

    # ---- import Cubism ------------------------------------------------

    # ---- examples menu --------------------------------------------------

    # ---- recent menu ----------------------------------------------------


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
    existing = [p for p in user_setting_dict.get(RECENT_KEY, []) if p != path]
    existing.insert(0, path)
    user_setting_dict[RECENT_KEY] = existing[:_RECENT_LIMIT]
