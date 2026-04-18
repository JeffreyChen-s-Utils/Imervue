"""
自訂鍵盤快捷鍵
Custom Keyboard Shortcuts — let users remap keyboard shortcuts.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import (
    user_setting_dict,
    schedule_save,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.shortcut_settings")


# ---------------------------------------------------------------------------
# Default shortcut map: action_id → (Qt key, Qt modifiers)
# Modifiers: 0 = none, Ctrl = ControlModifier, Shift = ShiftModifier
# ---------------------------------------------------------------------------

_CTRL = Qt.KeyboardModifier.ControlModifier.value
_SHIFT = Qt.KeyboardModifier.ShiftModifier.value
_ALT = Qt.KeyboardModifier.AltModifier.value
_CTRL_SHIFT = _CTRL | _SHIFT
_NONE = 0

def _k(key_enum) -> int:
    """Extract int value from a Qt.Key enum."""
    return key_enum.value if hasattr(key_enum, "value") else int(key_enum)


# Each entry: action_id → (key: int, modifiers: int)
DEFAULT_SHORTCUTS: dict[str, tuple[int, int]] = {
    "undo":             (_k(Qt.Key.Key_Z), _CTRL),
    "redo":             (_k(Qt.Key.Key_Y), _CTRL),
    "redo_alt":         (_k(Qt.Key.Key_Z), _CTRL_SHIFT),
    "copy":             (_k(Qt.Key.Key_C), _CTRL),
    "paste":            (_k(Qt.Key.Key_V), _CTRL),
    "search":           (_k(Qt.Key.Key_F), _CTRL),
    "fullscreen":       (_k(Qt.Key.Key_F), _NONE),
    "edit":             (_k(Qt.Key.Key_E), _NONE),
    "slideshow":        (_k(Qt.Key.Key_S), _NONE),
    "tags":             (_k(Qt.Key.Key_T), _NONE),
    "histogram":        (_k(Qt.Key.Key_H), _NONE),
    "fit_width":        (_k(Qt.Key.Key_W), _NONE),
    "fit_height":       (_k(Qt.Key.Key_W), _SHIFT),
    "bookmark":         (_k(Qt.Key.Key_B), _NONE),
    "rotate_cw":        (_k(Qt.Key.Key_R), _NONE),
    "rotate_ccw":       (_k(Qt.Key.Key_R), _SHIFT),
    "reset_view":       (_k(Qt.Key.Key_Home), _NONE),
    "search_alt":       (_k(Qt.Key.Key_Slash), _NONE),
    "favorite":         (_k(Qt.Key.Key_0), _NONE),
    "rate_1":           (_k(Qt.Key.Key_1), _NONE),
    "rate_2":           (_k(Qt.Key.Key_2), _NONE),
    "rate_3":           (_k(Qt.Key.Key_3), _NONE),
    "rate_4":           (_k(Qt.Key.Key_4), _NONE),
    "rate_5":           (_k(Qt.Key.Key_5), _NONE),
    "delete":           (_k(Qt.Key.Key_Delete), _NONE),
    "anim_toggle":      (_k(Qt.Key.Key_Space), _NONE),
    "anim_prev":        (_k(Qt.Key.Key_Comma), _NONE),
    "anim_next":        (_k(Qt.Key.Key_Period), _NONE),
    "anim_slower":      (_k(Qt.Key.Key_BracketLeft), _NONE),
    "anim_faster":      (_k(Qt.Key.Key_BracketRight), _NONE),
    "goto":             (_k(Qt.Key.Key_G), _CTRL),
    "theater":          (_k(Qt.Key.Key_Tab), _SHIFT),
    "pixel_view":       (_k(Qt.Key.Key_P), _SHIFT),
    "color_mode_cycle": (_k(Qt.Key.Key_M), _SHIFT),
    "history_back":     (_k(Qt.Key.Key_Left), _ALT),
    "history_forward":  (_k(Qt.Key.Key_Right), _ALT),
    "random_image":     (_k(Qt.Key.Key_X), _NONE),
    "split_view":       (_k(Qt.Key.Key_S), _SHIFT),
    "dual_page":        (_k(Qt.Key.Key_D), _SHIFT),
    "multi_monitor":    (_k(Qt.Key.Key_M), _CTRL_SHIFT),
}

# Translation key for each action (displayed in the dialog)
ACTION_DISPLAY_KEYS: dict[str, str] = {
    "undo":             "shortcut_action_undo",
    "redo":             "shortcut_action_redo",
    "redo_alt":         "shortcut_action_redo_alt",
    "copy":             "shortcut_action_copy",
    "paste":            "shortcut_action_paste",
    "search":           "shortcut_action_search",
    "fullscreen":       "shortcut_action_fullscreen",
    "edit":             "shortcut_action_edit",
    "slideshow":        "shortcut_action_slideshow",
    "tags":             "shortcut_action_tags",
    "histogram":        "shortcut_action_histogram",
    "fit_width":        "shortcut_action_fit_width",
    "fit_height":       "shortcut_action_fit_height",
    "bookmark":         "shortcut_action_bookmark",
    "rotate_cw":        "shortcut_action_rotate_cw",
    "rotate_ccw":       "shortcut_action_rotate_ccw",
    "reset_view":       "shortcut_action_reset_view",
    "search_alt":       "shortcut_action_search_alt",
    "favorite":         "shortcut_action_favorite",
    "rate_1":           "shortcut_action_rate_1",
    "rate_2":           "shortcut_action_rate_2",
    "rate_3":           "shortcut_action_rate_3",
    "rate_4":           "shortcut_action_rate_4",
    "rate_5":           "shortcut_action_rate_5",
    "delete":           "shortcut_action_delete",
    "anim_toggle":      "shortcut_action_anim_toggle",
    "anim_prev":        "shortcut_action_anim_prev",
    "anim_next":        "shortcut_action_anim_next",
    "anim_slower":      "shortcut_action_anim_slower",
    "anim_faster":      "shortcut_action_anim_faster",
    "goto":             "shortcut_action_goto",
    "theater":          "shortcut_action_theater",
    "pixel_view":       "shortcut_action_pixel_view",
    "color_mode_cycle": "shortcut_action_color_mode_cycle",
    "history_back":     "shortcut_action_history_back",
    "history_forward":  "shortcut_action_history_forward",
    "random_image":     "shortcut_action_random_image",
    "split_view":       "shortcut_action_split_view",
    "dual_page":        "shortcut_action_dual_page",
    "multi_monitor":    "shortcut_action_multi_monitor",
}

# English fallback names
ACTION_FALLBACKS: dict[str, str] = {
    "undo": "Undo", "redo": "Redo", "redo_alt": "Redo (Alt)",
    "copy": "Copy Image", "paste": "Paste Image", "search": "Search",
    "fullscreen": "Toggle Fullscreen", "edit": "Edit / Annotate",
    "slideshow": "Slideshow", "tags": "Tags & Albums",
    "histogram": "Toggle Histogram", "fit_width": "Fit to Width",
    "fit_height": "Fit to Height", "bookmark": "Toggle Bookmark",
    "rotate_cw": "Rotate Clockwise", "rotate_ccw": "Rotate Counter-clockwise",
    "reset_view": "Reset View", "search_alt": "Search (Alt)",
    "favorite": "Toggle Favorite",
    "rate_1": "Rate 1", "rate_2": "Rate 2", "rate_3": "Rate 3",
    "rate_4": "Rate 4", "rate_5": "Rate 5",
    "delete": "Delete",
    "anim_toggle": "Animation Play/Pause", "anim_prev": "Animation Prev Frame",
    "anim_next": "Animation Next Frame",
    "anim_slower": "Animation Slower", "anim_faster": "Animation Faster",
    "goto": "Go to Image",
    "theater": "Theater Mode",
    "pixel_view": "Pixel View",
    "color_mode_cycle": "Cycle Color Mode",
    "history_back": "History Back",
    "history_forward": "History Forward",
    "random_image": "Random Image",
    "split_view": "Split View",
    "dual_page": "Dual Page",
    "multi_monitor": "Multi-Monitor Window",
}


# ---------------------------------------------------------------------------
# Shortcut Manager — runtime singleton
# ---------------------------------------------------------------------------

class ShortcutManager:
    """Manages the mapping from (key, modifiers) → action_id at runtime."""

    def __init__(self):
        self._action_to_key: dict[str, tuple[int, int]] = {}
        self._key_to_action: dict[tuple[int, int], str] = {}
        self.load()

    def load(self):
        """Load shortcuts from user settings, falling back to defaults."""
        self._action_to_key = dict(DEFAULT_SHORTCUTS)
        saved = user_setting_dict.get("keyboard_shortcuts")
        if isinstance(saved, dict):
            for action_id, combo in saved.items():
                if (action_id in DEFAULT_SHORTCUTS
                        and isinstance(combo, list) and len(combo) == 2):
                    self._action_to_key[action_id] = (int(combo[0]), int(combo[1]))
        self._rebuild_reverse()

    def _rebuild_reverse(self):
        self._key_to_action.clear()
        for action_id, (key, mods) in self._action_to_key.items():
            self._key_to_action[(key, mods)] = action_id

    def get_action(self, key: int, modifiers: int) -> str | None:
        """Look up which action_id a key combo maps to."""
        # Mask out KeypadModifier and other noise
        mods = (modifiers.value if hasattr(modifiers, "value") else int(modifiers)) & (_CTRL | _SHIFT | _ALT)
        return self._key_to_action.get((key, mods))

    def get_key(self, action_id: str) -> tuple[int, int]:
        return self._action_to_key.get(action_id, (0, 0))

    def set_key(self, action_id: str, key: int, modifiers: int):
        """Bind ``action_id`` to (key, modifiers), unbinding any conflicting action.

        If another action was already claiming this combo, its binding is
        cleared to ``(0, 0)`` so the new mapping wins cleanly — otherwise
        ``_rebuild_reverse`` would resolve the conflict by dict-insertion
        order, which is invisible to callers and confusing in tests.
        """
        combo = (key, modifiers)
        for other_id, existing in list(self._action_to_key.items()):
            if other_id != action_id and existing == combo:
                self._action_to_key[other_id] = (0, 0)
        self._action_to_key[action_id] = combo
        self._rebuild_reverse()

    def save(self):
        """Persist current mapping to user settings."""
        data = {}
        for action_id, (key, mods) in self._action_to_key.items():
            data[action_id] = [key, mods]
        user_setting_dict["keyboard_shortcuts"] = data
        schedule_save()

    def reset_to_defaults(self):
        self._action_to_key = dict(DEFAULT_SHORTCUTS)
        self._rebuild_reverse()
        self.save()

    @staticmethod
    def key_to_string(key: int, modifiers: int) -> str:
        """Human-readable string for a key combo."""
        if key == 0:
            return ""
        m = modifiers.value if hasattr(modifiers, "value") else int(modifiers)
        seq = QKeySequence(m | key)
        return seq.toString(QKeySequence.SequenceFormat.NativeText)


# Global singleton
shortcut_manager = ShortcutManager()


# ---------------------------------------------------------------------------
# Key capture widget
# ---------------------------------------------------------------------------

class _KeyCaptureEdit(QLineEdit):
    """QLineEdit that captures the next key press as a shortcut."""
    key_captured = Signal(int, int)  # key, modifiers

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("...")
        self._key = 0
        self._mods = 0

    def set_key(self, key: int, modifiers: int):
        self._key = key
        self._mods = modifiers
        self.setText(ShortcutManager.key_to_string(key, modifiers))

    def keyPressEvent(self, event):
        key = event.key()
        # Ignore pure modifier presses
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
                   Qt.Key.Key_Meta):
            return
        raw = event.modifiers()
        mods = (raw.value if hasattr(raw, "value") else int(raw)) & (_CTRL | _SHIFT | _ALT)
        self._key = key
        self._mods = mods
        self.setText(ShortcutManager.key_to_string(key, mods))
        self.key_captured.emit(key, mods)
        self.clearFocus()


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class ShortcutSettingsDialog(QDialog):
    """Table-based dialog for remapping keyboard shortcuts."""

    def __init__(self, parent):
        super().__init__(parent)
        self._lang = language_wrapper.language_word_dict
        self.setWindowTitle(
            self._lang.get("shortcut_title", "Keyboard Shortcuts"))
        self.setMinimumSize(600, 500)
        self._edits: dict[str, _KeyCaptureEdit] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(self._lang.get(
            "shortcut_info",
            "Click a shortcut cell and press the new key combination."))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Table
        actions = list(DEFAULT_SHORTCUTS.keys())
        self._table = QTableWidget(len(actions), 3)
        self._table.setHorizontalHeaderLabels([
            self._lang.get("shortcut_col_action", "Action"),
            self._lang.get("shortcut_col_shortcut", "Shortcut"),
            self._lang.get("shortcut_col_default", "Default"),
        ])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        for row, action_id in enumerate(actions):
            # Action name
            display_key = ACTION_DISPLAY_KEYS.get(action_id, action_id)
            name = self._lang.get(display_key,
                                  ACTION_FALLBACKS.get(action_id, action_id))
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 0, name_item)

            # Current shortcut (editable capture widget)
            key, mods = shortcut_manager.get_key(action_id)
            edit = _KeyCaptureEdit()
            edit.set_key(key, mods)
            self._edits[action_id] = edit
            self._table.setCellWidget(row, 1, edit)

            # Default (read-only)
            dk, dm = DEFAULT_SHORTCUTS[action_id]
            default_item = QTableWidgetItem(
                ShortcutManager.key_to_string(dk, dm))
            default_item.setFlags(
                default_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 2, default_item)

        layout.addWidget(self._table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        reset_btn = QPushButton(
            self._lang.get("shortcut_reset", "Reset All to Default"))
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()

        save_btn = QPushButton(self._lang.get("shortcut_save", "Save"))
        save_btn.clicked.connect(self._save_and_close)
        cancel_btn = QPushButton(self._lang.get("export_cancel", "Cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _reset_all(self):
        for action_id, edit in self._edits.items():
            dk, dm = DEFAULT_SHORTCUTS[action_id]
            edit.set_key(dk, dm)

    def _save_and_close(self):
        for action_id, edit in self._edits.items():
            shortcut_manager.set_key(action_id, edit._key, edit._mods)
        shortcut_manager.save()
        self.accept()


def open_shortcut_settings(parent):
    dlg = ShortcutSettingsDialog(parent)
    dlg.exec()
