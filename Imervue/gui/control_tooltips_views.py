"""Help for tab bars and the rows and header sections of item views."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTabBar, QToolTip

from Imervue.gui.tooltip_text import plain_label, word


def refresh_tab_tips(widget: QTabBar) -> None:
    """Fill missing tab tips and regenerate the ones generated before, keeping authored tips."""
    previous = widget.property("imervueGeneratedTabTips") or []
    generated = []
    for index in range(widget.count()):
        if not widget.tabToolTip(index) or widget.tabToolTip(index) in previous:
            text = word("ui_tip_tab", name=plain_label(widget.tabText(index)))
            widget.setTabToolTip(index, text)
            generated.append(text)
    widget.setProperty("imervueGeneratedTabTips", generated)


def _item_tip(view: QAbstractItemView, event) -> bool:
    if isinstance(view, QHeaderView):
        section = view.logicalIndexAt(event.pos())
        if section < 0 or view.model() is None:
            return False
        if view.model().headerData(section, view.orientation(), Qt.ItemDataRole.ToolTipRole):
            return False
        value = view.model().headerData(section, view.orientation())
    else:
        index = view.indexAt(event.pos())
        if not index.isValid() or index.data(Qt.ItemDataRole.ToolTipRole):
            return False
        value = index.data(Qt.ItemDataRole.DisplayRole)
    if value is None or str(value) == "":
        return False
    QToolTip.showText(event.globalPos(), f"<qt>{escape(str(value))}</qt>", view.viewport())
    return True


def show_viewport_item_tip(watched, event) -> bool:
    """Show the hovered row's display text for an item-view viewport without its own help."""
    parent = watched.parentWidget()
    return (isinstance(parent, QAbstractItemView) and watched is parent.viewport()
            and not watched.toolTip() and _item_tip(parent, event))
