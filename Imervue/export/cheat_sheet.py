"""Printable keyboard-shortcut cheat-sheet PDF generator.

Walks the project's shortcut registry (``DEFAULT_SHORTCUTS`` +
``ACTION_DISPLAY_KEYS``) and emits an A4 / Letter PDF table the user can
print and pin next to their monitor. The currently-active language drives
the action labels, so the output matches the UI the user sees.

Pure layout logic — no Qt dialogs or file pickers in this module. The
GUI entry point lives in ``Imervue/menu/tip_menu.py`` and just prompts
for an output path before delegating here.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPainter, QPdfWriter

from Imervue.gui.shortcut_settings_dialog import (
    ACTION_DISPLAY_KEYS,
    ACTION_FALLBACKS,
    DEFAULT_SHORTCUTS,
    shortcut_manager,
)
from Imervue.multi_language.language_wrapper import language_wrapper

logger = logging.getLogger("Imervue.export.cheat_sheet")

PAGE_SIZES: dict[str, QPageSize.PageSizeId] = {
    "A4": QPageSize.PageSizeId.A4,
    "Letter": QPageSize.PageSizeId.Letter,
}

_HEADER_PT = 18
_BODY_PT = 11
_ACTION_PT = 11
_KEY_PT = 11

_PADDING_PX = 10
_ROW_HEIGHT_PX = 36


@dataclass(frozen=True)
class CheatSheetOptions:
    """Layout options for ``generate_cheat_sheet``."""

    page_size: str = "A4"
    title: str = ""
    margin_mm: float = 12.0
    dpi: int = 300


def collect_shortcut_rows() -> list[tuple[str, str]]:
    """Return ``[(action_label, key_combo_text), ...]`` for every shortcut.

    Reads any user-customised key bindings from ``shortcut_manager`` and
    falls back to the default registry. Action labels respect the active
    language; keys are rendered as plain "Ctrl+Shift+P"-style combos.
    """
    lang = language_wrapper.language_word_dict
    rows: list[tuple[str, str]] = []
    for action_id in DEFAULT_SHORTCUTS:
        label = lang.get(
            ACTION_DISPLAY_KEYS.get(action_id, ""),
            ACTION_FALLBACKS.get(action_id, action_id),
        )
        rows.append((label, _action_key_text(action_id)))
    return rows


def _action_key_text(action_id: str) -> str:
    """Resolve the user's current binding for ``action_id`` as a string.

    The shortcut manager owns customised bindings; we fall back to the
    static default registry only when the manager is absent (e.g. headless
    test environments).
    """
    binding = None
    if hasattr(shortcut_manager, "get_key"):
        try:
            binding = shortcut_manager.get_key(action_id)
        except KeyError:
            binding = None
    if binding is None:
        binding = DEFAULT_SHORTCUTS.get(action_id)
    if not binding:
        return ""
    key, modifiers = binding
    return _format_key_combo(int(key), int(modifiers))


def _format_key_combo(key: int, modifiers: int) -> str:
    """Render a (key, modifiers) pair as 'Ctrl+Shift+P' text."""
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtGui import QKeySequence
    seq_value = key | int(modifiers)
    seq = QKeySequence(seq_value)
    text = seq.toString(QKeySequence.SequenceFormat.NativeText)
    if text:
        return text
    # Fallback for keys QKeySequence does not stringify (rare).
    parts = []
    if modifiers & int(_Qt.KeyboardModifier.ControlModifier):
        parts.append("Ctrl")
    if modifiers & int(_Qt.KeyboardModifier.ShiftModifier):
        parts.append("Shift")
    if modifiers & int(_Qt.KeyboardModifier.AltModifier):
        parts.append("Alt")
    parts.append(QKeySequence(key).toString())
    return "+".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------


def generate_cheat_sheet(out_path: str, options: CheatSheetOptions) -> str:
    """Write a printable shortcut PDF to ``out_path``. Returns the path."""
    rows = collect_shortcut_rows()
    writer = _make_pdf_writer(out_path, options)
    painter = QPainter(writer)
    try:
        _render_pdf(painter, writer, rows, options)
    finally:
        painter.end()
    return out_path


def _make_pdf_writer(out_path: str, options: CheatSheetOptions) -> QPdfWriter:
    writer = QPdfWriter(out_path)
    writer.setResolution(options.dpi)
    page_id = PAGE_SIZES.get(options.page_size, QPageSize.PageSizeId.A4)
    layout = QPageLayout(
        QPageSize(page_id),
        QPageLayout.Orientation.Portrait,
        QMarginsF(options.margin_mm, options.margin_mm,
                  options.margin_mm, options.margin_mm),
        QPageLayout.Unit.Millimeter,
    )
    writer.setPageLayout(layout)
    writer.setTitle("Imervue Shortcuts")
    return writer


def _render_pdf(
    painter: QPainter,
    writer: QPdfWriter,
    rows: list[tuple[str, str]],
    options: CheatSheetOptions,
) -> None:
    page_w = writer.width()
    page_h = writer.height()

    cursor_y = _draw_title(painter, page_w, options)
    cursor_y += _PADDING_PX

    rows_per_page = max(1, (page_h - cursor_y - _PADDING_PX) // _ROW_HEIGHT_PX)
    for idx, (label, combo) in enumerate(rows):
        if idx and idx % rows_per_page == 0:
            writer.newPage()
            cursor_y = _draw_title(painter, page_w, options) + _PADDING_PX
        _draw_row(painter, page_w, cursor_y, label, combo)
        cursor_y += _ROW_HEIGHT_PX


def _draw_title(painter: QPainter, page_w: int, options: CheatSheetOptions) -> int:
    """Paint the document title and return the next free Y position."""
    lang = language_wrapper.language_word_dict
    title = options.title or lang.get(
        "cheat_sheet_title", "Imervue Keyboard Shortcuts",
    )
    font = QFont("Segoe UI")
    font.setPointSize(_HEADER_PT)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(_PADDING_PX, _PADDING_PX + _HEADER_PT * 2,
                     page_w - 2 * _PADDING_PX, _HEADER_PT * 3,
                     int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                     title)
    return _HEADER_PT * 4


def _draw_row(
    painter: QPainter,
    page_w: int,
    y: int,
    label: str,
    combo: str,
) -> None:
    label_font = QFont("Segoe UI")
    label_font.setPointSize(_ACTION_PT)
    painter.setFont(label_font)
    label_w = (page_w - 2 * _PADDING_PX) // 2
    painter.drawText(_PADDING_PX, y,
                     label_w, _ROW_HEIGHT_PX,
                     int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                     label)

    combo_font = QFont("Consolas")
    combo_font.setPointSize(_KEY_PT)
    combo_font.setBold(True)
    painter.setFont(combo_font)
    painter.drawText(_PADDING_PX + label_w, y,
                     label_w, _ROW_HEIGHT_PX,
                     int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                     combo)
