"""Application preferences dialog.

Centralised dialog for runtime-tunable user options that don't fit any
domain-specific dialog. Currently exposes:

* **VRAM tile-cache limit** — overrides the auto-detected GPU memory budget.

The dialog persists changes through ``user_setting_dict`` + ``schedule_save``
so they round-trip across restarts. A restart is required for the VRAM limit
to take effect because it is consumed during ``GPUImageView.initializeGL``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.themes import DEFAULT_THEME_NAME, list_themes
from Imervue.system.ui_scale import (
    UI_SCALE_DEFAULT_PERCENT,
    UI_SCALE_MAX_PERCENT,
    UI_SCALE_MIN_PERCENT,
    UI_SCALE_STEP_PERCENT,
)
from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

VRAM_MIN_MB = 256
VRAM_MAX_MB = 8192
VRAM_DEFAULT_MB = 1536  # 1.5 GB conservative fallback
VRAM_STEP_MB = 128


class PreferencesDialog(QDialog):
    """Modal preferences dialog editing values in ``user_setting_dict``."""

    def __init__(self, parent: ImervueMainWindow | None = None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("preferences_title", "Preferences"))
        self.setModal(True)
        self.resize(440, 320)

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_vram_form())
        layout.addLayout(self._build_ui_scale_form())
        layout.addLayout(self._build_theme_form())
        layout.addStretch(1)
        layout.addWidget(self._build_button_box())

    # ------------------------------------------------------------------
    # Form sections
    # ------------------------------------------------------------------

    def _build_vram_form(self) -> QFormLayout:
        lang = language_wrapper.language_word_dict
        form = QFormLayout()

        self._auto_vram = QCheckBox(
            lang.get("preferences_vram_auto", "Auto-detect from GPU")
        )
        auto = bool(user_setting_dict.get("vram_limit_auto", True))
        self._auto_vram.setChecked(auto)

        self._vram_spin = QSpinBox()
        self._vram_spin.setRange(VRAM_MIN_MB, VRAM_MAX_MB)
        self._vram_spin.setSingleStep(VRAM_STEP_MB)
        self._vram_spin.setSuffix(" MB")
        self._vram_spin.setValue(
            int(user_setting_dict.get("vram_limit_mb", VRAM_DEFAULT_MB))
        )
        self._vram_spin.setEnabled(not auto)
        self._auto_vram.toggled.connect(
            lambda checked: self._vram_spin.setEnabled(not checked)
        )

        hint = QLabel(
            lang.get(
                "preferences_vram_hint",
                "Tile-cache budget for the GPU viewer. Restart required.",
            )
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)

        form.addRow(
            lang.get("preferences_vram_label", "GPU tile-cache limit:"),
            self._vram_spin,
        )
        form.addRow("", self._auto_vram)
        form.addRow(hint)
        return form

    def _build_ui_scale_form(self) -> QFormLayout:
        lang = language_wrapper.language_word_dict
        form = QFormLayout()

        self._ui_scale_spin = QSpinBox()
        self._ui_scale_spin.setRange(UI_SCALE_MIN_PERCENT, UI_SCALE_MAX_PERCENT)
        self._ui_scale_spin.setSingleStep(UI_SCALE_STEP_PERCENT)
        self._ui_scale_spin.setSuffix(" %")
        self._ui_scale_spin.setValue(
            int(user_setting_dict.get("ui_scale_percent", UI_SCALE_DEFAULT_PERCENT))
        )

        hint = QLabel(
            lang.get(
                "preferences_ui_scale_hint",
                "Scales every widget by adjusting the application font. Restart required.",
            )
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)

        form.addRow(
            lang.get("preferences_ui_scale_label", "UI scale:"),
            self._ui_scale_spin,
        )
        form.addRow(hint)
        return form

    def _build_theme_form(self) -> QFormLayout:
        lang = language_wrapper.language_word_dict
        form = QFormLayout()

        self._theme_combo = QComboBox()
        current = str(user_setting_dict.get("theme", DEFAULT_THEME_NAME))
        for theme in list_themes():
            self._theme_combo.addItem(theme.label, userData=theme.name)
            if theme.name == current:
                self._theme_combo.setCurrentIndex(self._theme_combo.count() - 1)

        hint = QLabel(
            lang.get(
                "preferences_theme_hint",
                "Restart required for the new theme to fully apply.",
            )
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)

        form.addRow(lang.get("preferences_theme_label", "Theme:"), self._theme_combo)
        form.addRow(hint)
        return form

    def _build_button_box(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        return buttons

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _accept(self) -> None:
        user_setting_dict["vram_limit_auto"] = bool(self._auto_vram.isChecked())
        user_setting_dict["vram_limit_mb"] = int(self._vram_spin.value())
        user_setting_dict["ui_scale_percent"] = int(self._ui_scale_spin.value())
        user_setting_dict["theme"] = str(self._theme_combo.currentData())
        schedule_save()
        self.accept()


def open_preferences_dialog(parent: ImervueMainWindow) -> None:
    dlg = PreferencesDialog(parent)
    dlg.exec()
