"""Pose-group picker dock for the Puppet workspace.

A pose group is a set of drawables of which exactly one is visible (a
weapon swap, a costume, a hand shape). The dock lists every group on the
loaded document with a combo box of its members; picking one makes it the
visible member through :meth:`PuppetCanvas.set_pose_active`. A group
shows its first member until another is picked.

The dock rebuilds on ``canvas.document_loaded`` and follows
``canvas.pose_changed``, so Reset to rest (which puts every group back on
its first member) shows in the combo boxes too.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFormLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas


class PoseDock(QDockWidget):
    """Right-dockable panel: one member picker per document pose group."""

    def __init__(self, canvas: PuppetCanvas, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("puppet_pose_dock", "Pose"), parent)
        self._canvas = canvas
        self._combos: dict[str, QComboBox] = {}
        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidget(self._inner)
        scroll.setWidgetResizable(True)
        self.setWidget(scroll)

        canvas.document_loaded.connect(self._rebuild_from_canvas)
        canvas.pose_changed.connect(self._show_member)
        self._rebuild_from_canvas()

    def combos(self) -> dict[str, QComboBox]:
        """The member picker of each pose group, keyed by group id."""
        return dict(self._combos)

    def _rebuild_from_canvas(self) -> None:
        self._clear()
        document = self._canvas.document()
        groups = [g for g in (document.pose_groups if document else []) if g.drawables]
        if not groups:
            self._layout.addWidget(self._build_empty_state())
            self._layout.addStretch(1)
            return
        active = self._canvas.active_pose()
        form = QFormLayout()
        for group in groups:
            combo = QComboBox()
            combo.addItems(group.drawables)
            current = active.get(group.id)
            combo.setCurrentIndex(
                group.drawables.index(current) if current in group.drawables else 0)
            combo.currentTextChanged.connect(
                lambda member, group_id=group.id: self._canvas.set_pose_active(
                    group_id, member))
            self._combos[group.id] = combo
            form.addRow(document.display_names.get(group.id, group.id), combo)
        self._layout.addLayout(form)
        self._layout.addStretch(1)

    def _show_member(self, group_id: str, member: str) -> None:
        """Move the group's picker to ``member`` without re-applying it."""
        combo = self._combos.get(group_id)
        if combo is None or combo.currentText() == member:
            return
        combo.blockSignals(True)
        combo.setCurrentText(member)
        combo.blockSignals(False)

    def _clear(self) -> None:
        self._combos.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                _delete_layout(item.layout())

    @staticmethod
    def _build_empty_state() -> QLabel:
        lang = language_wrapper.language_word_dict
        label = QLabel(lang.get(
            "puppet_pose_empty", "No pose groups — load a puppet that defines them."))
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888; padding: 8px;")
        return label


def _delete_layout(layout) -> None:
    """Delete every widget of a detached layout, then the layout itself."""
    while layout.count():
        widget = layout.takeAt(0).widget()
        if widget is not None:
            widget.deleteLater()
    layout.deleteLater()
