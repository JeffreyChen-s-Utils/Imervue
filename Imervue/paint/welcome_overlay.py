"""Centered welcome hint shown over a fresh, untouched canvas.

Industry convention (Photoshop start screen, Procreate gallery,
Krita welcome screen) is to drop a "what can I do here?" affordance
in front of the user the very first time they see a blank canvas.
This module is the Paint workspace's take on that pattern:

* a translucent rounded panel positioned at the canvas centre,
* drag-drop hint as the headline,
* "New tab" / "Open file…" buttons that route to the existing file
  menu bridge so we don't duplicate logic,
* optionally a short list of recent files for one-click resume.

Visibility is fully driven by :class:`PaintWorkspace` — show on a
fresh / untouched seed canvas, hide on the first real edit or when
an image is loaded. The widget itself never auto-shows.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Maximum number of recent-file rows surfaced in the panel. Beyond
# that the panel grows tall enough to hide what's underneath.
_MAX_RECENT_ROWS = 3


class WelcomeHint(QFrame):
    """Translucent centred panel inviting the user to start work.

    Emits :attr:`new_requested` / :attr:`open_requested` /
    :attr:`recent_requested` so the workspace stays the single
    authority on what each action means (route to file menu bridge,
    invoke the right dialog, etc.). The widget knows about layout
    and paint, nothing about the underlying file ops.
    """

    new_requested = Signal()
    open_requested = Signal()
    recent_requested = Signal(str)   # absolute path of the chosen recent

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            WelcomeHint {
                background: rgba(40, 40, 40, 200);
                border-radius: 12px;
            }
            QLabel {
                color: #eaeaea;
                background: transparent;
            }
            QLabel#welcome_title {
                font-size: 16px;
            }
            QLabel#welcome_subtitle {
                color: #b0b0b0;
                font-size: 12px;
            }
            QLabel#welcome_recent_label {
                color: #b0b0b0;
                font-size: 11px;
            }
            QPushButton {
                background: rgba(255, 255, 255, 30);
                color: #f0f0f0;
                border: 1px solid rgba(255, 255, 255, 60);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 50);
            }
            QPushButton#welcome_recent_row {
                text-align: left;
                padding: 4px 10px;
            }
            """,
        )

        self._title = QLabel(self)
        self._title.setObjectName("welcome_title")
        self._title.setText("Drag an image or PSD here")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFont(QFont(self._title.font().family(), 12, QFont.Weight.Bold))

        self._subtitle = QLabel(self)
        self._subtitle.setObjectName("welcome_subtitle")
        self._subtitle.setText("or pick a starting point")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._new_btn = QPushButton("New tab", self)
        self._new_btn.setToolTip("Open an empty canvas in a new tab (Ctrl+T)")
        self._open_btn = QPushButton("Open file…", self)
        self._open_btn.setToolTip(
            "Pick an image or .psd from disk to open in this workspace",
        )
        self._new_btn.clicked.connect(self.new_requested)
        self._open_btn.clicked.connect(self.open_requested)

        self._recent_label = QLabel(self)
        self._recent_label.setObjectName("welcome_recent_label")
        self._recent_label.setText("Recent")
        self._recent_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._recent_buttons: list[QPushButton] = []

        self._build_layout()
        self.setVisible(False)
        self.adjustSize()

    # ---- public API ---------------------------------------------------------

    def set_translations(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        new_label: str | None = None,
        open_label: str | None = None,
        recent_label: str | None = None,
        new_tooltip: str | None = None,
        open_tooltip: str | None = None,
    ) -> None:
        """Allow the workspace to push localised strings in.

        Each parameter is optional; ``None`` keeps the current text.
        Splitting the localisation out of the constructor keeps the
        widget importable from tests that don't want to drag in the
        language wrapper.
        """
        if title is not None:
            self._title.setText(title)
        if subtitle is not None:
            self._subtitle.setText(subtitle)
        if new_label is not None:
            self._new_btn.setText(new_label)
        if open_label is not None:
            self._open_btn.setText(open_label)
        if recent_label is not None:
            self._recent_label.setText(recent_label)
        if new_tooltip is not None:
            self._new_btn.setToolTip(new_tooltip)
        if open_tooltip is not None:
            self._open_btn.setToolTip(open_tooltip)

    def set_recent_paths(self, paths: list[str]) -> None:
        """Re-populate the "Recent" section with up to N paths.

        Each row is a left-aligned button labelled with the file's
        basename; clicking emits :attr:`recent_requested` with the
        absolute path the workspace can then route through its file
        menu bridge. Passing an empty list hides the recent section
        entirely so the panel stays compact for first-time users.
        """
        from pathlib import Path

        for btn in self._recent_buttons:
            btn.deleteLater()
        self._recent_buttons.clear()
        trimmed = list(paths)[:_MAX_RECENT_ROWS]
        self._recent_label.setVisible(bool(trimmed))
        for path in trimmed:
            label = Path(path).name or path
            btn = QPushButton(label, self)
            btn.setObjectName("welcome_recent_row")
            btn.setToolTip(path)
            btn.clicked.connect(
                lambda _checked=False, p=path: self.recent_requested.emit(p),
            )
            self._recent_layout.addWidget(btn)
            self._recent_buttons.append(btn)
        self.adjustSize()

    def position_centred(self, parent_w: int, parent_h: int) -> None:
        """Reposition self at the centre of the parent given its size.

        Pulled out of ``resizeEvent`` so the workspace can call it
        on document changes / window resizes without spawning Qt
        events that ricochet through the canvas's GL paint path.
        """
        self.adjustSize()
        x = max(0, (parent_w - self.width()) // 2)
        y = max(0, (parent_h - self.height()) // 2)
        self.move(x, y)

    # ---- internals ---------------------------------------------------------

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(6)
        outer.addWidget(self._title)
        outer.addWidget(self._subtitle)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch(1)
        button_row.addWidget(self._new_btn)
        button_row.addWidget(self._open_btn)
        button_row.addStretch(1)
        outer.addSpacing(6)
        outer.addLayout(button_row)

        outer.addSpacing(10)
        outer.addWidget(self._recent_label)
        self._recent_layout = QVBoxLayout()
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setSpacing(2)
        outer.addLayout(self._recent_layout)
