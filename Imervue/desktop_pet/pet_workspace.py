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
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_window import PetWindow
from Imervue.multi_language.language_wrapper import language_wrapper


def _tr(key: str, default: str) -> str:
    """Tiny shortcut to keep call sites readable. Every UI
    string in this module goes through the wrapper so the labels
    swap when the user changes language at runtime."""
    return language_wrapper.language_word_dict.get(key, default)

logger = logging.getLogger("Imervue.desktop_pet.pet_workspace")

DEFAULT_EXAMPLE_PUPPET = "examples/puppet/march_7th.puppet"
"""Repo-root relative path used for the test that verifies the
constant still points inside ``examples/puppet/``. The actual
runtime resolution goes through :func:`examples_dir` so packaged
builds (Nuitka EXE, pip install) find the bundled rig wherever
Imervue was installed instead of relying on the user's CWD."""


def _resolve_bundled_example() -> Path | None:
    """Return the absolute path to the bundled March 7th rig, or
    ``None`` when the file isn't present (some dev checkouts strip
    examples for size). Tries the frozen-safe ``examples_dir()``
    first, then falls back to a CWD-relative lookup so the workspace
    keeps working when the user runs from the repo root without an
    install."""
    from Imervue.system.app_paths import examples_dir

    for root in (examples_dir(), Path.cwd()):
        candidate = root / "puppet" / "march_7th.puppet"
        if candidate.is_file():
            return candidate
        # Some layouts use ``examples/puppet/...`` directly under
        # the search root rather than splitting examples_dir already
        # ending in "examples". Cover that too.
        candidate = root / "examples" / "puppet" / "march_7th.puppet"
        if candidate.is_file():
            return candidate
    return None


class PetWorkspace(QWidget):
    """The control-panel tab. Owns one :class:`PetWindow`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pet_window: PetWindow | None = None
        self._tray = None  # set by the main window after construction
        self._build_ui()
        self._restore_persisted_session()

    # ---- persisted session restore -----------------------------

    def _restore_persisted_session(self) -> None:
        """If the user's previous Imervue session had a rig and /
        or a pet script loaded, re-load them so the pet returns to
        that state. ``show_on_launch`` separately controls whether
        the overlay shows itself automatically."""
        settings = pet_settings.load()
        last_path = str(settings.get("last_rig_path", "") or "")
        if last_path and Path(last_path).is_file() and self.load_puppet(last_path):
            self._reapply_persisted_toggles(settings)
            if settings.get("show_on_launch"):
                self._show_check.setChecked(True)
        # PetWindow restores the script itself from settings on
        # construction; refresh the workspace's label so the UI
        # mirrors what's actually loaded.
        script_path = str(settings.get("script_path", "") or "")
        if hasattr(self, "_current_script_label"):
            self._current_script_label.setText(
                self._format_script_label(script_path),
            )

    def _reapply_persisted_toggles(self, settings: dict) -> None:
        """Re-tick the workspace's checkboxes so the visible UI
        state matches the persisted state. The pet window already
        read its own state from settings during __init__; this is
        about syncing the workspace's checkboxes."""
        drivers = settings.get("drivers", {}) or {}
        for key, checkbox in (
            ("auto_idle", self._idle_check),
            ("idle_motion", self._idle_motion_check),
            ("auto_blink", self._blink_check),
            ("drag_track", self._drag_check),
            ("mic_lipsync", self._mic_check),
            ("webcam_tracking", self._webcam_check),
        ):
            if drivers.get(key):
                checkbox.setChecked(True)

    # ---- construction ------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(
            "<b>" + _tr(
                "desktop_pet_section_title",
                "Desktop Pet — overlay your puppet on the desktop",
            ) + "</b>",
        )
        layout.addWidget(title)

        layout.addWidget(self._build_rig_group())
        layout.addWidget(self._build_window_group())
        layout.addWidget(self._build_drivers_group())
        layout.addWidget(self._build_script_group())
        layout.addStretch(1)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #888;")
        layout.addWidget(self._status)

    def _build_rig_group(self) -> QGroupBox:
        group = QGroupBox(_tr("desktop_pet_group_rig", "Rig"))
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self._open_button = QPushButton(
            _tr("desktop_pet_open_puppet", "Open Puppet…"),
        )
        self._open_button.clicked.connect(self._on_open_puppet)
        row.addWidget(self._open_button)
        self._open_example_button = QPushButton(
            _tr("desktop_pet_load_example", "Load bundled March 7th"),
        )
        self._open_example_button.clicked.connect(self._on_open_example)
        row.addWidget(self._open_example_button)
        row.addStretch(1)
        layout.addLayout(row)

        self._current_rig_label = QLabel(
            _tr("desktop_pet_no_rig", "No rig loaded"),
        )
        self._current_rig_label.setStyleSheet("color: #888;")
        layout.addWidget(self._current_rig_label)
        return group

    def _build_window_group(self) -> QGroupBox:
        group = QGroupBox(_tr("desktop_pet_group_window", "Window"))
        layout = QVBoxLayout(group)
        settings = pet_settings.load()

        self._show_check = QCheckBox(
            _tr("desktop_pet_show", "Show pet on desktop"),
        )
        self._show_check.toggled.connect(self._on_show_toggled)
        layout.addWidget(self._show_check)

        self._click_through_check = QCheckBox(
            _tr(
                "desktop_pet_click_through",
                "Click-through (let mouse events pass to the desktop)",
            ),
        )
        self._click_through_check.setChecked(bool(settings["click_through"]))
        self._click_through_check.toggled.connect(self._on_click_through_toggled)
        layout.addWidget(self._click_through_check)

        self._anchor_check = QCheckBox(
            _tr("desktop_pet_anchor", "Lock position (ignore drags)"),
        )
        self._anchor_check.setChecked(bool(settings["anchor_locked"]))
        self._anchor_check.toggled.connect(self._on_anchor_toggled)
        layout.addWidget(self._anchor_check)

        self._on_bottom_check = QCheckBox(
            _tr(
                "desktop_pet_on_bottom",
                "Always on bottom (desktop widget — sits behind every window)",
            ),
        )
        self._on_bottom_check.setChecked(bool(settings["always_on_bottom"]))
        self._on_bottom_check.toggled.connect(self._on_always_on_bottom_toggled)
        layout.addWidget(self._on_bottom_check)

        self._fullscreen_check = QCheckBox(
            _tr(
                "desktop_pet_hide_fullscreen",
                "Hide when another app goes fullscreen",
            ),
        )
        self._fullscreen_check.setChecked(bool(settings["hide_on_fullscreen"]))
        self._fullscreen_check.toggled.connect(self._on_fullscreen_toggled)
        layout.addWidget(self._fullscreen_check)

        self._speech_check = QCheckBox(
            _tr("desktop_pet_speech", "Speech bubble on click"),
        )
        self._speech_check.setChecked(bool(settings["speech_enabled"]))
        self._speech_check.toggled.connect(self._on_speech_toggled)
        layout.addWidget(self._speech_check)

        # Size combo
        row = QHBoxLayout()
        row.addWidget(QLabel(_tr("desktop_pet_size_label", "Size:")))
        self._size_combo = QComboBox()
        self._size_combo.addItems(["small", "medium", "large"])
        self._size_combo.setCurrentText(str(settings["size_preset"]))
        self._size_combo.currentTextChanged.connect(self._on_size_changed)
        row.addWidget(self._size_combo)
        row.addStretch(1)
        layout.addLayout(row)

        # Opacity slider — slider expresses tenths (10-100) for
        # integer precision; converted to 0.1 - 1.0 float on apply.
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
        layout.addLayout(row)

        # Snap threshold spin box
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
        layout.addLayout(row)
        return group

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
        group = QGroupBox(_tr("desktop_pet_group_script", "Pet script"))
        layout = QVBoxLayout(group)
        settings = pet_settings.load()

        row = QHBoxLayout()
        self._load_script_button = QPushButton(
            _tr("desktop_pet_load_script", "Load script…"),
        )
        self._load_script_button.clicked.connect(self._on_load_script)
        row.addWidget(self._load_script_button)
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
        self._current_script_label.setStyleSheet("color: #888;")
        layout.addWidget(self._current_script_label)
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
            _tr("desktop_pet_open_puppet", "Open Puppet…"),
            "",
            "Puppet files (*.puppet)",
        )
        if path:
            self.load_puppet(path)

    def _on_open_example(self) -> None:   # pragma: no cover - depends on bundled file
        candidate = _resolve_bundled_example()
        if candidate is None:
            self._status.setText(
                _tr(
                    "desktop_pet_example_missing",
                    "Bundled example not found at {path} — install or run "
                    "from the repository root.",
                ).format(path=DEFAULT_EXAMPLE_PUPPET),
            )
            return
        self.load_puppet(candidate)

    def load_puppet(self, path: str | Path) -> bool:
        """Load ``path`` into the pet overlay. Returns True on
        success. The status label surfaces failure detail.

        On success the **Show pet on desktop** checkbox is ticked
        and the overlay is shown — without that, the user clicks
        "Load…" and sees nothing happen, since the pet's default
        state is hidden. Setting ``checked`` after the load
        triggers the existing ``_on_show_toggled`` slot which
        calls ``window.show()`` for us."""
        window = self._ensure_pet_window()
        if not window.load_puppet_file(path):
            self._status.setText(
                _tr("desktop_pet_load_failed", "Failed to load {path}").format(
                    path=path,
                ),
            )
            return False
        self._current_rig_label.setText(
            _tr("desktop_pet_loaded", "Loaded: {name}").format(
                name=Path(str(path)).name,
            ),
        )
        self._status.setText("")
        # Auto-show on first successful load so the user sees
        # immediate feedback from the click. setChecked emits
        # ``toggled`` only when the state actually changes, so
        # a re-load on an already-visible pet is a cheap no-op
        # rather than a hide-then-show flicker.
        self._show_check.setChecked(True)
        return True

    # ---- pet script --------------------------------------------

    def _format_script_label(self, path: str) -> str:
        if not path:
            return _tr(
                "desktop_pet_script_default",
                "(Using built-in default voice)",
            )
        return _tr(
            "desktop_pet_script_loaded", "Loaded: {name}",
        ).format(name=Path(path).name)

    def _on_load_script(self) -> None:   # pragma: no cover - Qt UI
        path, _ = QFileDialog.getOpenFileName(
            self,
            _tr("desktop_pet_load_script_title", "Load pet script"),
            "",
            "Pet script (*.json *.petscript.json)",
        )
        if path:
            self.load_script(path)

    def load_script(self, path: str | Path) -> bool:
        """Load a ``.petscript.json`` into the pet overlay's
        script engine. Returns ``True`` on success. The status
        label surfaces failure detail."""
        window = self._ensure_pet_window()
        if not window.load_script_file(path):
            self._status.setText(
                _tr(
                    "desktop_pet_script_failed", "Failed to load script: {path}",
                ).format(path=path),
            )
            return False
        self._current_script_label.setText(
            self._format_script_label(str(path)),
        )
        self._status.setText("")
        return True

    def _on_reset_script(self) -> None:
        """Drop the user script and revert to the built-in
        greetings. The pet window does the actual reset; this
        slot just refreshes the label + status."""
        if self._pet_window is not None:
            self._pet_window.reset_script_to_default()
        # Whether or not we had a window, persist the empty path
        # so the next launch doesn't reload a stale script.
        from Imervue.desktop_pet import settings as _settings
        _settings.update(script_path="")
        self._current_script_label.setText(self._format_script_label(""))
        self._status.setText("")

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

    def _on_anchor_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_anchor_locked(bool(checked))

    def _on_always_on_bottom_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_always_on_bottom(bool(checked))

    def _on_fullscreen_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_hide_on_fullscreen(bool(checked))

    def _on_speech_toggled(self, checked: bool) -> None:
        self._ensure_pet_window().set_speech_enabled(bool(checked))

    def _on_opacity_changed(self, percent: int) -> None:
        value = max(10, min(100, int(percent))) / 100.0
        self._opacity_label.setText(f"{int(value * 100)}%")
        self._ensure_pet_window().set_pet_opacity(value)

    def _on_snap_changed(self, px: int) -> None:
        self._ensure_pet_window().set_snap_threshold(int(px))

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
                _tr(
                    "desktop_pet_mic_missing",
                    "Mic lip-sync needs sounddevice — pip install sounddevice",
                ),
            )
            self._mic_check.blockSignals(True)
            self._mic_check.setChecked(False)
            self._mic_check.blockSignals(False)

    def _on_webcam_toggled(self, checked: bool) -> None:
        ok = self._ensure_pet_window().set_webcam_tracking_enabled(bool(checked))
        if checked and not ok:
            self._status.setText(
                _tr(
                    "desktop_pet_webcam_missing",
                    "Webcam tracking needs opencv-python + mediapipe",
                ),
            )
            self._webcam_check.blockSignals(True)
            self._webcam_check.setChecked(False)
            self._webcam_check.blockSignals(False)
