"""Puppet workspace Qt shell, child ownership and action identity."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QStatusBar,
)
from Imervue.gui.control_tooltips import enable_control_tooltips
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.canvas import PuppetCanvas
from Imervue.puppet.expression_dock import ExpressionDock
from Imervue.puppet.idle_driver import IdleDriver
from Imervue.puppet.idle_motion_cycler import IdleMotionCycler
from Imervue.puppet.batch_export import BatchMotionExporter
from Imervue.puppet.bone_tree_dock import BoneTreeDock
from Imervue.puppet.ndi_output import NDIOutput
from Imervue.puppet.virtual_camera import VirtualCameraOutput
from Imervue.puppet.vts_api import VTubeStudioServer
from Imervue.puppet.input_engine import InputEngine
from Imervue.puppet.motion_dock import MotionDock
from Imervue.puppet.motion_recorder import MotionRecorder
from Imervue.puppet.parameter_dock import ParameterDock
from Imervue.puppet.pose_dock import PoseDock
from Imervue.puppet.recorder import RecordingSession
from Imervue.puppet.webcam_tracker import WebcamTracker
from Imervue.puppet.workspace_import import PuppetImportMixin
from Imervue.puppet.workspace_live import PuppetLiveMixin
from Imervue.puppet.workspace_menus import RECENT_KEY, PuppetMenusMixin
from Imervue.puppet.workspace_files import PuppetFilesMixin
from Imervue.puppet.workspace_authoring import PuppetAuthoringMixin
from Imervue.puppet.workspace_keyframes import PuppetKeyframesMixin
from Imervue.puppet.workspace_reset import PuppetResetMixin
from Imervue.puppet.workspace_input import PuppetInputMixin
from Imervue.puppet.workspace_validation import PuppetValidationMixin
from Imervue.puppet.workspace_export import PuppetExportMixin
from Imervue.puppet.workspace_motion_edit import PuppetMotionEditMixin
from Imervue.puppet.workspace_motion_record import PuppetMotionRecordMixin
from Imervue.puppet.workspace_audio import PuppetAudioMixin
from Imervue.puppet.workspace_files import _push_recent

__all__ = ["PuppetWorkspace", "_push_recent", "RECENT_KEY", "QFileDialog"]


class PuppetWorkspace(
    PuppetFilesMixin, PuppetAuthoringMixin, PuppetKeyframesMixin, PuppetResetMixin,
    PuppetInputMixin, PuppetValidationMixin, PuppetExportMixin, PuppetMotionEditMixin,
    PuppetMotionRecordMixin, PuppetAudioMixin, PuppetMenusMixin, PuppetLiveMixin,
    PuppetImportMixin, QMainWindow,
):
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
        from Imervue.puppet.workspace_ui import build_welcome, configure_inspectors
        self._welcome = build_welcome(self)
        configure_inspectors(self)
        enable_control_tooltips(self)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.property("initialInspectorSized"):
            from Imervue.puppet.workspace_ui import size_inspectors
            from Imervue.system.qt_timers import call_later
            self.setProperty("initialInspectorSized", True)
            call_later(0, self, lambda: size_inspectors(self))

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
        self._pose_dock = PoseDock(self._canvas, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._pose_dock)
        self.tabifyDockWidget(self._expression_dock, self._parameter_dock)
        self.tabifyDockWidget(self._expression_dock, self._pose_dock)
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
        self._webcam.state_changed.connect(self._on_webcam_state_changed)
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

    def _canvas_reset_view(self) -> None:
        self._canvas.reset_view()

    def _announce(self, key: str, fallback: str, **fmt) -> None:
        self._status_label.setText(
            language_wrapper.language_word_dict.get(key, fallback).format(**fmt),
        )

    def input_engine(self) -> InputEngine:
        return self._input_engine

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        self.shutdown()
        super().closeEvent(event)

    def idle_motion_cycler(self) -> IdleMotionCycler:
        return self._idle_motion_cycler

    def _refresh_status_for_no_document(self) -> None:
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_empty",
                "No puppet loaded — use Open to load a .puppet file.",
            ),
        )

    @property
    def _status(self) -> QLabel:
        return self._status_label
