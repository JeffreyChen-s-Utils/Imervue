"""Expression selector dock for the Puppet workspace.

Lists every :class:`Expression` on the loaded document as a togglable
button. Activating a row pushes the expression onto the canvas's
active-expression stack so its parameter overrides layer on top of
slider values; deactivating it removes the entry. Multiple expressions
can stack — matches the Live2D convention where e.g. a smile +
surprise overlay add together.

The dock listens to ``canvas.document_loaded`` and rebuilds rows so
swapping documents refreshes the list without manual wiring.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas


class ExpressionDock(QDockWidget):
    """Right-dockable panel: one button per document expression."""

    expression_toggled = Signal(str, bool)
    """Emitted after the canvas state changes — ``(name, is_active)``.
    UI tests assert against this without poking the canvas internals."""

    def __init__(self, canvas: PuppetCanvas, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("puppet_expressions_dock", "Expressions"), parent)
        self._canvas = canvas
        self._buttons: dict[str, QPushButton] = {}
        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidget(self._inner)
        scroll.setWidgetResizable(True)
        self.setWidget(scroll)

        canvas.document_loaded.connect(self._rebuild_from_canvas)
        self._rebuild_from_canvas()

    def buttons(self) -> dict[str, QPushButton]:
        """Expose the per-name buttons so tests can simulate clicks
        without going through the actual QApplication event loop."""
        return dict(self._buttons)

    def toggle_expression(self, name: str) -> bool:
        """Programmatic toggle entry point (also used by the button
        click). Returns the resulting active state."""
        if name in self._canvas.active_expressions():
            self._canvas.remove_expression(name)
            active = False
        else:
            self._canvas.add_expression(name)
            active = name in self._canvas.active_expressions()
        button = self._buttons.get(name)
        if button is not None:
            button.blockSignals(True)
            button.setChecked(active)
            button.blockSignals(False)
        self.expression_toggled.emit(name, active)
        return active

    # ---- rebuild --------------------------------------------------------

    def _rebuild_from_canvas(self) -> None:
        self._clear_rows()
        document = self._canvas.document()
        if document is None or not document.expressions:
            self._layout.addWidget(self._build_empty_state())
            self._layout.addStretch(1)
            return
        active = set(self._canvas.active_expressions())
        for expression in document.expressions:
            button = QPushButton(expression.name)
            button.setCheckable(True)
            button.setChecked(expression.name in active)
            button.clicked.connect(
                lambda _checked=False, name=expression.name: self.toggle_expression(name),
            )
            self._buttons[expression.name] = button
            self._layout.addWidget(button)
        self._layout.addStretch(1)

    def _clear_rows(self) -> None:
        self._buttons.clear()
        for i in range(self._layout.count() - 1, -1, -1):
            item = self._layout.takeAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_empty_state(self) -> QLabel:
        lang = language_wrapper.language_word_dict
        label = QLabel(
            lang.get(
                "puppet_expressions_empty",
                "No expressions — load a puppet that defines them.",
            ),
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888; padding: 8px;")
        return label
