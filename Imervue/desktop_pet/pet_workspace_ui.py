"""Desktop Pet tab — widget construction.

Builds the heading, the Rig group and the tabbed Window / Live drivers /
Pet script / Global hotkeys pages, restoring each control from the saved pet
settings and wiring it to its slot.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_workspace_files import _PET_SCRIPT
from Imervue.desktop_pet.pet_workspace_hotkeys import hotkey_conflict_notice, saved_hotkeys
from Imervue.desktop_pet.pet_workspace_toggles import _tr


class PetWorkspaceUiMixin:
    """Widget construction of :class:`PetWorkspace`."""

    def _build_ui(self) -> None:
        from Imervue.gui.panel_scroll import PanelScrollArea
        from Imervue.system.ui_scale import scaled_px

        self.setObjectName("petWorkspace")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(scaled_px(18),) * 4)
        layout.setSpacing(scaled_px(14))
        title = QLabel(_tr("desktop_pet_tab_title", "Desktop Pet"))
        title.setObjectName("workspaceHeading")
        font = QFont(title.font())
        font.setPointSizeF(max(1, font.pointSizeF()) + 5)
        font.setWeight(QFont.Weight.DemiBold)
        title.setFont(font)
        layout.addWidget(title)
        description = QLabel(_tr(
            "desktop_pet_workspace_hint",
            "Choose a character, then adjust its appearance and behaviour.",
        ))
        description.setObjectName("workspaceDescription")
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addWidget(self._build_rig_group())

        self._settings_tabs = QTabWidget()
        self._settings_tabs.setObjectName("petSettingsTabs")
        for builder in (self._build_window_group, self._build_drivers_group,
                        self._build_script_group, self._build_hotkey_group):
            group = builder()
            title = group.title()
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(*(scaled_px(12),) * 4)
            page_layout.addWidget(group)
            page_layout.addStretch()
            self._settings_tabs.addTab(PanelScrollArea(page), title)
        layout.addWidget(self._settings_tabs, 1)

        self._status = QLabel(hotkey_conflict_notice(saved_hotkeys()))
        self._status.setObjectName("workspaceDescription")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

    def _build_rig_group(self) -> QGroupBox:
        group = QGroupBox(_tr("desktop_pet_group_rig", "Rig"))
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self._open_button = QPushButton(
            _tr("desktop_pet_open_puppet", "Open Puppet…"),
        )
        self._open_button.setProperty("primary", True)
        self._open_button.clicked.connect(self._on_open_puppet)
        row.addWidget(self._open_button)
        self._open_example_button = QPushButton(
            _tr("desktop_pet_load_example", "Load bundled Imeru"),
        )
        self._open_example_button.clicked.connect(self._on_open_example)
        row.addWidget(self._open_example_button)
        row.addStretch(1)
        layout.addLayout(row)

        self._current_rig_label = QLabel(
            _tr("desktop_pet_no_rig", "No rig loaded"),
        )
        self._current_rig_label.setObjectName("workspaceDescription")
        self._current_rig_label.setWordWrap(True)
        layout.addWidget(self._current_rig_label)
        return group

    def _build_window_group(self) -> QGroupBox:
        group = QGroupBox(_tr("desktop_pet_group_window", "Window"))
        layout = QVBoxLayout(group)
        settings = pet_settings.load()

        self._show_check = self._window_check(
            _tr("desktop_pet_show", "Show pet on desktop"), None, self._on_show_toggled)
        self._launch_check = self._window_check(
            _tr("desktop_pet_show_on_launch", "Show the pet when Imervue starts"),
            settings["show_on_launch"], self._on_show_on_launch_toggled)
        self._click_through_check = self._window_check(
            _tr(
                "desktop_pet_click_through",
                "Click-through (let mouse events pass to the desktop)",
            ),
            settings["click_through"], self._on_click_through_toggled)
        self._anchor_check = self._window_check(
            _tr("desktop_pet_anchor", "Lock position (ignore drags)"),
            settings["anchor_locked"], self._on_anchor_toggled)
        self._on_bottom_check = self._window_check(
            _tr(
                "desktop_pet_on_bottom",
                "Always on bottom (desktop widget — sits behind every window)",
            ),
            settings["always_on_bottom"], self._on_always_on_bottom_toggled)
        self._fullscreen_check = self._window_check(
            _tr(
                "desktop_pet_hide_fullscreen",
                "Hide when another app goes fullscreen",
            ),
            settings["hide_on_fullscreen"], self._on_fullscreen_toggled)
        self._speech_check = self._window_check(
            _tr("desktop_pet_speech", "Speech bubble on click"),
            settings["speech_enabled"], self._on_speech_toggled)
        for box in (self._show_check, self._launch_check, self._click_through_check,
                    self._anchor_check, self._on_bottom_check, self._fullscreen_check,
                    self._speech_check):
            layout.addWidget(box)

        layout.addLayout(self._build_size_row(settings))
        layout.addLayout(self._build_opacity_row(settings))
        layout.addLayout(self._build_snap_row(settings))
        return group

    @staticmethod
    def _window_check(text: str, saved, on_toggle) -> QCheckBox:
        """Checkbox restored from ``saved`` (``None`` = leave unchecked), wired to ``on_toggle``."""
        box = QCheckBox(text)
        if saved is not None:
            box.setChecked(bool(saved))
        box.toggled.connect(on_toggle)
        return box

    def _build_size_row(self, settings: dict) -> QHBoxLayout:
        """Size preset combo restored from the saved preset."""
        row = QHBoxLayout()
        row.addWidget(QLabel(_tr("desktop_pet_size_label", "Size:")))
        self._size_combo = QComboBox()
        # Shown in the UI language; the item data is the preset name PetWindow takes.
        for preset, fallback in (("small", "Small"), ("medium", "Medium"), ("large", "Large")):
            self._size_combo.addItem(_tr(f"desktop_pet_size_{preset}", fallback), preset)
        self._size_combo.setCurrentIndex(
            max(0, self._size_combo.findData(str(settings["size_preset"]))),
        )
        self._size_combo.currentIndexChanged.connect(
            lambda _index: self._on_size_changed(self._size_combo.currentData()),
        )
        row.addWidget(self._size_combo)
        row.addStretch(1)
        return row

    def _build_opacity_row(self, settings: dict) -> QHBoxLayout:
        """Opacity slider with its percentage readout.

        The slider expresses tenths (10-100) for integer precision; the value
        is converted to a 0.1 - 1.0 float on apply.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel(_tr("desktop_pet_opacity_label", "Opacity:")))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setMinimum(10)
        self._opacity_slider.setMaximum(100)
        self._opacity_slider.setValue(int(float(settings["opacity"]) * 100))
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        row.addWidget(self._opacity_slider, 1)
        self._opacity_label = QLabel(f"{int(float(settings['opacity']) * 100)}%")
        self._opacity_label.setMinimumWidth(40)
        row.addWidget(self._opacity_label)
        return row

    def _build_snap_row(self, settings: dict) -> QHBoxLayout:
        """Edge-snap threshold in pixels (0-200)."""
        row = QHBoxLayout()
        row.addWidget(QLabel(
            _tr("desktop_pet_snap_label", "Edge-snap threshold (px):"),
        ))
        self._snap_spin = QSpinBox()
        self._snap_spin.setMinimum(0)
        self._snap_spin.setMaximum(200)
        self._snap_spin.setValue(int(settings["snap_threshold"]))
        self._snap_spin.valueChanged.connect(self._on_snap_changed)
        row.addWidget(self._snap_spin)
        row.addStretch(1)
        return row

    def _build_drivers_group(self) -> QGroupBox:
        group = QGroupBox(_tr("desktop_pet_group_drivers", "Live drivers"))
        layout = QVBoxLayout(group)

        self._idle_check = QCheckBox(
            _tr("desktop_pet_auto_idle", "Auto idle (breath + drift)"),
        )
        self._idle_check.toggled.connect(self._on_idle_toggled)
        layout.addWidget(self._idle_check)

        self._idle_motion_check = QCheckBox(
            _tr("desktop_pet_idle_motion", "Idle motions (random cycle)"),
        )
        self._idle_motion_check.toggled.connect(self._on_idle_motion_toggled)
        layout.addWidget(self._idle_motion_check)

        self._blink_check = QCheckBox(_tr("desktop_pet_auto_blink", "Auto-blink"))
        self._blink_check.toggled.connect(self._on_blink_toggled)
        layout.addWidget(self._blink_check)

        self._drag_check = QCheckBox(
            _tr("desktop_pet_drag_track", "Drag-track head (look at cursor)"),
        )
        self._drag_check.toggled.connect(self._on_drag_toggled)
        layout.addWidget(self._drag_check)

        self._gaze_check = QCheckBox(
            _tr("desktop_pet_mouse_gaze", "Mouse gaze (eyes follow cursor)"),
        )
        self._gaze_check.toggled.connect(self._on_gaze_toggled)
        layout.addWidget(self._gaze_check)

        self._mic_check = QCheckBox(
            _tr("desktop_pet_mic_lipsync", "Mic lip-sync (needs sounddevice)"),
        )
        self._mic_check.toggled.connect(self._on_mic_toggled)
        layout.addWidget(self._mic_check)

        self._webcam_check = QCheckBox(
            _tr(
                "desktop_pet_webcam",
                "Webcam tracking (needs opencv-python + mediapipe)",
            ),
        )
        self._webcam_check.toggled.connect(self._on_webcam_toggled)
        layout.addWidget(self._webcam_check)
        return group

    def _build_script_group(self) -> QGroupBox:
        """Custom pet voice — point at a ``.petscript.json`` to
        replace the built-in greetings + per-hit-area / per-motion
        lines + scheduled chimes. The actual JSON schema lives in
        :mod:`Imervue.desktop_pet.pet_script`; this group is just
        the load / reset surface."""
        group = QGroupBox(_tr("desktop_pet_group_script", _PET_SCRIPT))
        layout = QVBoxLayout(group)
        settings = pet_settings.load()

        row = QHBoxLayout()
        self._load_script_button = QPushButton(
            _tr("desktop_pet_load_script", "Load script…"),
        )
        self._load_script_button.clicked.connect(self._on_load_script)
        row.addWidget(self._load_script_button)
        self._edit_script_button = QPushButton(
            _tr("desktop_pet_edit_script", "Edit script…"),
        )
        self._edit_script_button.clicked.connect(self._on_edit_script)
        row.addWidget(self._edit_script_button)
        self._reset_script_button = QPushButton(
            _tr("desktop_pet_reset_script", "Reset to default"),
        )
        self._reset_script_button.clicked.connect(self._on_reset_script)
        row.addWidget(self._reset_script_button)
        row.addStretch(1)
        layout.addLayout(row)

        self._current_script_label = QLabel(
            self._format_script_label(settings.get("script_path", "")),
        )
        self._current_script_label.setObjectName("workspaceDescription")
        self._current_script_label.setWordWrap(True)
        layout.addWidget(self._current_script_label)
        return group
