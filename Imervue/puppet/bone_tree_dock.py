"""Bone-hierarchy editor — QTreeView over :attr:`Deformer.parent`.

The runtime's ``compose_drawable_vertices`` already honours the
parent chain (topological sort), so anything the user does here
changes how the rig renders without further wiring.

The widget supports:

* **Read** — every deformer in the active document shows up under its
  ``parent`` (root-level deformers sit at the top).
* **Reparent** — drag a deformer onto another row to set its
  ``parent`` to that row's id.
* **Detach** — drag onto the empty area to clear ``parent`` (the
  deformer becomes a root).
* **Select** — clicking a row emits :attr:`deformer_selected` so the
  workspace can highlight the same deformer elsewhere (parameter
  dock filter, mesh-edit focus, …).

Kept Qt-thin — the data model is just ``document.deformers``; we
read it on rebuild and write back on drop.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.puppet.canvas import PuppetCanvas
    from Imervue.puppet.document import Deformer


_ID_ROLE = Qt.ItemDataRole.UserRole


class BoneTreeDock(QDockWidget):
    """Tree view of every deformer in the loaded document.

    Each row's ``UserRole`` stores the deformer id so drag-and-drop /
    selection handlers can resolve back to a :class:`Deformer`
    without a separate lookup."""

    deformer_selected = Signal(str)
    """Fires with the deformer id when the user clicks a row."""

    hierarchy_changed = Signal()
    """Fires after any reparent — the workspace re-renders so the
    canvas reflects the new FK order immediately."""

    def __init__(self, canvas: PuppetCanvas, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("puppet_bone_tree_dock", "Bones"), parent)
        self._canvas = canvas
        self._inner = QWidget()
        layout = QVBoxLayout(self._inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            lang.get("puppet_bone_tree_col_id", "ID"),
            lang.get("puppet_bone_tree_col_type", "Type"),
        ])
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree.itemClicked.connect(self._on_item_clicked)
        # Right-click anywhere on the tree clears the selection. We
        # use the customContextMenuRequested signal rather than
        # overriding mousePressEvent so the default drag-and-drop path
        # stays untouched.
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(
            self._on_tree_context_request,
        )
        layout.addWidget(self._tree)

        self._empty_state = QLabel(
            lang.get(
                "puppet_bone_tree_empty",
                "No deformers yet — add one from the toolbar.",
            ),
        )
        self._empty_state.setWordWrap(True)
        self._empty_state.setStyleSheet("color: #888; padding: 8px;")
        layout.addWidget(self._empty_state)

        self.setWidget(self._inner)

        # The dock listens for new documents and (when present) the
        # canvas's deformer change signal. The canvas may or may not
        # emit such a signal yet — connect defensively.
        canvas.document_loaded.connect(self._rebuild)
        self._rebuild()

    # ---- public --------------------------------------------------------

    def tree(self) -> QTreeWidget:
        return self._tree

    def rebuild(self) -> None:
        """Public re-entry point — workspace calls this after toolbar
        actions add / remove deformers."""
        self._rebuild()

    def clear_selection(self) -> None:
        """Drop the tree-row highlight without emitting
        ``deformer_selected`` — used when the canvas already cleared
        its overlay (e.g. via a right-click) and we just need the
        tree state to match."""
        self._tree.clearSelection()

    def _on_tree_context_request(self, _pos) -> None:
        """Right-click in the tree clears the selection on both
        sides. Emits an empty ``deformer_selected`` so the canvas
        overlay drops in lockstep."""
        self._tree.clearSelection()
        self.deformer_selected.emit("")

    # ---- rebuild -------------------------------------------------------

    def _rebuild(self) -> None:
        self._tree.clear()
        document = self._canvas.document()
        deformers = list(document.deformers) if document is not None else []
        if not deformers:
            self._tree.setVisible(False)
            self._empty_state.setVisible(True)
            return
        self._tree.setVisible(True)
        self._empty_state.setVisible(False)
        items: dict[str, QTreeWidgetItem] = {}
        for deformer in deformers:
            items[deformer.id] = self._row_for(deformer)
        # First pass — every deformer gets a row. Second pass — wire
        # parent relationships (a child can appear in document order
        # before its parent, so we can't link during the first pass).
        for deformer in deformers:
            item = items[deformer.id]
            parent_item = items.get(deformer.parent) if deformer.parent else None
            if parent_item is None:
                self._tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
        self._tree.expandAll()

    def _row_for(self, deformer: Deformer) -> QTreeWidgetItem:
        item = QTreeWidgetItem([deformer.id, deformer.type])
        item.setData(0, _ID_ROLE, deformer.id)
        item.setFlags(item.flags()
                      | Qt.ItemFlag.ItemIsDragEnabled
                      | Qt.ItemFlag.ItemIsDropEnabled)
        return item

    # ---- slots ---------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        deformer_id = item.data(0, _ID_ROLE)
        if isinstance(deformer_id, str):
            self.deformer_selected.emit(deformer_id)

    def reparent(self, child_id: str, new_parent: str | None) -> bool:
        """Programmatic equivalent of the drag-and-drop path — also
        the entry point used by tests so we don't need a real drop
        event. Returns ``True`` when the document was mutated."""
        document = self._canvas.document()
        if document is None:
            return False
        child = document.deformer(child_id)
        if child is None:
            return False
        if new_parent is not None:
            parent = document.deformer(new_parent)
            if parent is None or parent.id == child.id:
                return False
            # Disallow cycles — walk the prospective parent's chain
            # and refuse if the child appears in it.
            cursor = parent
            while cursor is not None:
                if cursor.id == child.id:
                    return False
                cursor = document.deformer(cursor.parent) if cursor.parent else None
        child.parent = new_parent
        self._rebuild()
        self.hierarchy_changed.emit()
        return True
