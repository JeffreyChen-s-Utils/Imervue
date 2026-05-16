"""Desktop Pet — control panel (Tab 5).

The tab itself never shows the puppet; it owns a :class:`PetWindow`
(top-level overlay) and exposes the toggles the user needs to
launch / configure / dismiss it. Single overlay per session — the
window is reused across rig swaps so the GL context and uploaded
textures survive across "open a different .puppet" actions.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet.pet_window import PetWindow

logger = logging.getLogger("Imervue.desktop_pet.pet_workspace")

DEFAULT_EXAMPLE_PUPPET = "examples/puppet/march_7th.puppet"
"""Reasonable starter rig — the bundled March 7th Cubism
conversion is the same default the Puppet tab's Examples menu
offers. Lets the user launch a pet without first having to author
or import their own ``.puppet`` archive."""


class PetWorkspace(QWidget):
    """The control-panel tab. Owns one :class:`PetWindow`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pet_window: PetWindow | None = None
        self._tray = None  # set by the main window after construction
        self._build_ui()

    # ---- construction ------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("<b>Desktop Pet</b> — overlay your puppet on the desktop")
        layout.addWidget(title)

        layout.addWidget(self._build_rig_group())
        layout.addWidget(self._build_window_group())
        layout.addWidget(self._build_drivers_group())
        layout.addStretch(1)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #888;")
        layout.addWidget(self._status)

    def _build_rig_group(self) -> QGroupBox:
        group = QGroupBox("Rig")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self._open_button = QPushButton("Open Puppet…")
        self._open_button.clicked.connect(self._on_open_puppet)
        row.addWidget(self._open_button)
        self._open_example_button = QPushButton("Load bundled March 7th")
        self._open_example_button.clicked.connect(self._on_open_example)
        row.addWidget(self._open_example_button)
        row.addStretch(1)
        layout.addLayout(row)

        self._current_rig_label = QLabel("No rig loaded")
        self._current_rig_label.setStyleSheet("color: #888;")
        layout.addWidget(self._current_rig_label)
        return group

    def _build_window_group(self) -> QGroupBox:
        group = QGroupBox("Window")
        layout = QVBoxLayout(group)

        self._show_check = QCheckBox("Show pet on desktop")
        self._show_check.toggled.connect(self._on_show_toggled)
        layout.addWidget(self._show_check)

        self._click_through_check = QCheckBox(
            "Click-through (let mouse events pass to the desktop)",
        )
        self._click_through_check.toggled.connect(self._on_click_through_toggled)
        layout.addWidget(self._click_through_check)

        row = QHBoxLayout()
        row.addWidget(QLabel("Size:"))
        self._size_combo = QComboBox()
        self._size_combo.addItems(["small", "medium", "large"])
        self._size_combo.setCurrentText("medium")
        self._size_combo.currentTextChanged.connect(self._on_size_changed)
        row.addWidget(self._size_combo)
        row.addStretch(1)
        layout.addLayout(row)
        return group

    def _build_drivers_group(self) -> QGroupBox:
        group = QGroupBox("Live drivers")
        layout = QVBoxLayout(group)

        self._idle_check = QCheckBox("Auto idle (breath + drift)")
        self._idle_check.toggled.connect(self._on_idle_toggled)
        layout.addWidget(self._idle_check)

        self._idle_motion_check = QCheckBox("Idle motions (random cycle)")
        self._idle_motion_check.toggled.connect(self._on_idle_motion_toggled)
        layout.addWidget(self._idle_motion_check)

        self._blink_check = QCheckBox("Auto-blink")
        self._blink_check.toggled.connect(self._on_blink_toggled)
        layout.addWidget(self._blink_check)

        self._drag_check = QCheckBox("Drag-track head (look at cursor)")
        self._drag_check.toggled.connect(self._on_drag_toggled)
        layout.addWidget(self._drag_check)

        self._mic_check = QCheckBox("Mic lip-sync (needs sounddevice)")
        self._mic_check.toggled.connect(self._on_mic_toggled)
        layout.addWidget(self._mic_check)

        self._webcam_check = QCheckBox(
            "Webcam tracking (needs opencv-python + mediapipe)",
        )
        self._webcam_check.toggled.connect(self._on_webcam_toggled)
        layout.addWidget(self._webcam_check)
        return group

    # ---- pet-window lifecycle ----------------------------------

    def _ensure_pet_window(self) -> PetWindow:
        """Create the overlay on first need. Lazy so a user who
        never enables the tab never instantiates the GL widget."""
        if self._pet_window is None:
            self._pet_window = PetWindow()
            self._pet_window.visibility_changed.connect(
                self._on_pet_visibility_changed,
            )
        return self._pet_window

    def pet_window(self) -> PetWindow | None:
        """Test hook — returns the overlay if it's been created."""
        return self._pet_window

    def attach_tray(self, tray) -> None:
        """Workspace doesn't own the tray (the main window does),
        but it does need a back-reference so dock toggles can mirror
        into the tray menu's state. Optional — main window calls it
        after construction; tests skip it."""
        self._tray = tray

    # ---- rig loading -------------------------------------------

    def _on_open_puppet(self) -> None:   # pragma: no cover - Qt UI
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open puppet for desktop pet",
            "",
            "Puppet files (*.puppet)",
        )
        if path:
            self.load_puppet(path)

    def _on_open_example(self) -> None:   # pragma: no cover - depends on bundled file
        # The bundled rig sits next to whatever CWD the user
        # launched Imervue from. Tests bypass this via
        # ``load_puppet`` directly.
        candidate = Path(DEFAULT_EXAMPLE_PUPPET)
        if not candidate.is_file():
            self._status.setText(
                f"Bundled example not found at {candidate} — install or run "
                "from the repository root.",
            )
            return
        self.load_puppet(candidate)

    def load_puppet(self, path: str | Path) -> bool:
        """Load ``path`` into the pet overlay. Returns True on
        success. The status label surfaces failure detail."""
        window = self._ensure_pet_window()
        if not window.load_puppet_file(path):
            self._status.setText(f"Failed to load {path}")
            return False
        self._current_rig_label.setText(f"Loaded: {Path(str(path)).name}")
        self._status.setText("")
        return True

    # ---- visibility --------------------------------------------

    def _on_show_toggled(self, checked: bool) -> None:
        window = self._ensure_pet_window()
        if checked:
            window.show()
        else:
            window.hide()

    def _on_pet_visibility_changed(self, visible: bool) -> None:
        # Block-signals dance to avoid feeding the toggled signal
        # back into ``_on_show_toggled``.
        self._show_check.blockSignals(True)
        try:
            self._show_check.setChecked(visible)
        finally:
            self._show_check.blockSignals(False)

    def _on_click_through_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_click_through(bool(checked))

    def _on_size_changed(self, preset: str) -> None:
        if self._pet_window is None:
            return
        self._pet_window.set_size_preset(preset)

    # ---- drivers -----------------------------------------------

    def _on_idle_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_auto_idle_enabled(bool(checked))

    def _on_idle_motion_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_idle_motion_enabled(bool(checked))

    def _on_blink_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_auto_blink_enabled(bool(checked))

    def _on_drag_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_drag_track_enabled(bool(checked))

    def _on_mic_toggled(self, checked: bool) -> None:
        ok = self._ensure_pet_window().set_mic_lipsync_enabled(bool(checked))
        if checked and not ok:
            self._status.setText(
                "Mic lip-sync needs sounddevice — pip install sounddevice",
            )
            self._mic_check.blockSignals(True)
            self._mic_check.setChecked(False)
            self._mic_check.blockSignals(False)

    def _on_webcam_toggled(self, checked: bool) -> None:
        ok = self._ensure_pet_window().set_webcam_tracking_enabled(bool(checked))
        if checked and not ok:
            self._status.setText(
                "Webcam tracking needs opencv-python + mediapipe",
            )
            self._webcam_check.blockSignals(True)
            self._webcam_check.setChecked(False)
            self._webcam_check.blockSignals(False)
