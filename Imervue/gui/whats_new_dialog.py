"""What's-New dialog showing release-note bullets for one or more versions.

Pops up automatically the first time a user launches a new version — the
last-seen version is stored in ``user_setting_dict`` so we never re-show
the same release. The dialog is also reachable on demand from the
Instructions menu so curious users can browse the full history.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.release_notes import (
    RELEASE_HISTORY,
    ReleaseEntry,
    current_app_version,
    releases_since,
)
from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

_LAST_SEEN_KEY = "whats_new_last_seen_version"


class WhatsNewDialog(QDialog):
    """Modal dialog rendering a list of release entries."""

    def __init__(
        self,
        entries: list[ReleaseEntry],
        parent: ImervueMainWindow | None = None,
    ):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("whats_new_title", "What's New"))
        self.setModal(True)
        self.resize(560, 480)

        layout = QVBoxLayout(self)

        header = QLabel(
            lang.get(
                "whats_new_header",
                "Here's what changed since you last opened Imervue.",
            )
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        layout.addWidget(self._build_scroll_body(entries))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _build_scroll_body(entries: list[ReleaseEntry]) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(12)

        for entry in entries:
            body_layout.addWidget(_render_release_entry(entry))
        body_layout.addStretch(1)

        scroll.setWidget(body)
        return scroll


def _render_release_entry(entry: ReleaseEntry) -> QWidget:
    """One version block: version header + bulleted feature list."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    title = QLabel(f"<b>v{entry.version}</b>")
    title.setTextFormat(Qt.TextFormat.RichText)
    layout.addWidget(title)

    bullets_html = "<ul style='margin-left:16px;'>" + "".join(
        f"<li>{_escape(b)}</li>" for b in entry.bullets
    ) + "</ul>"
    body = QLabel(bullets_html)
    body.setTextFormat(Qt.TextFormat.RichText)
    body.setWordWrap(True)
    body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(body)

    return widget


def _escape(text: str) -> str:
    """Minimal HTML escape — release-note text is hand-written, not user input."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def show_whats_new_if_upgraded(parent: ImervueMainWindow) -> bool:
    """Auto-show the dialog when the current version is newer than last-seen.

    Returns ``True`` when the dialog was shown. Updates the stored
    last-seen version regardless so users acknowledging the upgrade
    don't get nagged again on the next launch.
    """
    seen = str(user_setting_dict.get(_LAST_SEEN_KEY, ""))
    fresh = releases_since(seen)
    if not fresh:
        return False
    dlg = WhatsNewDialog(fresh, parent=parent)
    dlg.exec()
    user_setting_dict[_LAST_SEEN_KEY] = current_app_version()
    schedule_save()
    return True


def open_whats_new_dialog(parent: ImervueMainWindow | None = None) -> None:
    """Manual entry point — always shows the full release history."""
    dlg = WhatsNewDialog(list(RELEASE_HISTORY), parent=parent)
    dlg.exec()
    user_setting_dict[_LAST_SEEN_KEY] = current_app_version()
    schedule_save()
