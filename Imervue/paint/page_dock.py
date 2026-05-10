"""Comic-project page browser dock.

Mirrors MediBang Paint Pro's "Comic Project" page list. The dock
binds to ``workspace._paint_project`` (a :class:`PaintProject`) and
presents one row per page with a thumbnail, a name, and the usual
add / remove / duplicate / move-up / move-down / apply-template
actions. Selecting a page swaps the active canvas's document with
the page's document so the user can paint on it directly.

The dock degrades gracefully when no project is bound — every action
is a no-op until the workspace creates one (via the upcoming
"File → New Project" menu entry), so adding the dock to the layout
is safe even on first launch.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


PAGE_THUMB_PX = 64


class PageDock(QDockWidget):
    """Page-list panel for a multi-page comic / illustration project."""

    # Emitted when the user picks a page from the list. Workspace
    # listens and swaps the active canvas's document.
    page_selected = Signal(int)

    def __init__(self, workspace: PaintWorkspace, parent=None):
        lang = language_wrapper.language_word_dict
        super().__init__(lang.get("paint_dock_pages", "Pages"), parent)
        self._workspace = workspace

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)

        self._status = QLabel(
            lang.get(
                "paint_pages_no_project",
                "(no project — File ▸ New Project to start)",
            ),
        )
        self._status.setStyleSheet("color: #888;")
        layout.addWidget(self._status)

        self._list = QListWidget()
        self._list.setIconSize(QPixmap(PAGE_THUMB_PX, PAGE_THUMB_PX).size())
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.itemDoubleClicked.connect(self._on_double_clicked)
        # F2 enters inline rename on the selected page — matches the
        # file-tree convention so artists who learned the gesture there
        # don't have to memorise a different one for the page list.
        # ``EditKeyPressed`` is Qt's "F2 enters edit mode" trigger.
        from PySide6.QtWidgets import QAbstractItemView
        self._list.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked,
        )
        layout.addWidget(self._list, stretch=1)

        controls = QHBoxLayout()
        for key, fallback, slot, tip_key, tip_fallback in (
            ("paint_pages_add", "+", self._on_add,
             "paint_pages_add_tooltip", "Append a new blank page"),
            ("paint_pages_remove", "−", self._on_remove,
             "paint_pages_remove_tooltip", "Remove the selected page"),
            ("paint_pages_duplicate", "⧉", self._on_duplicate,
             "paint_pages_duplicate_tooltip",
             "Duplicate the selected page below it"),
            ("paint_pages_up", "↑", lambda: self._on_move(up=True),
             "paint_pages_up_tooltip", "Move the selected page up"),
            ("paint_pages_down", "↓", lambda: self._on_move(up=False),
             "paint_pages_down_tooltip", "Move the selected page down"),
        ):
            btn = QToolButton()
            btn.setText(lang.get(key, fallback))
            btn.clicked.connect(slot)
            btn.setToolTip(lang.get(tip_key, tip_fallback))
            controls.addWidget(btn)

        # "Apply template" — popup of available page templates that
        # creates a new page seeded with the chosen template's layout.
        template_btn = QToolButton()
        template_btn.setText(
            lang.get("paint_pages_template", "From template…"),
        )
        template_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        template_btn.setMenu(self._build_template_menu())
        controls.addWidget(template_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.setWidget(body)
        self._suspend = False
        self.refresh()

    # ---- public ----------------------------------------------------------

    def refresh(self) -> None:
        """Re-build the list against the workspace's current project."""
        project = self._project()
        self._suspend = True
        try:
            self._list.clear()
            if project is None or project.page_count == 0:
                self._status.setText(
                    language_wrapper.language_word_dict.get(
                        "paint_pages_no_project",
                        "(no project — File ▸ New Project to start)",
                    ),
                )
                return
            self._status.setText(
                language_wrapper.language_word_dict.get(
                    "paint_pages_count", "{name} — {n} page(s)",
                ).format(name=project.name, n=project.page_count),
            )
            for idx, page in enumerate(project.pages):
                item = QListWidgetItem(f"{idx + 1}. {page.name}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                item.setData(Qt.ItemDataRole.UserRole, idx)
                item.setIcon(_thumbnail_icon(page))
                self._list.addItem(item)
            self._list.setCurrentRow(project.active_page_index)
        finally:
            self._suspend = False

    # ---- private ---------------------------------------------------------

    def _project(self):
        return getattr(self._workspace, "_paint_project", None)   # noqa: SLF001

    def _build_template_menu(self) -> QMenu:
        from Imervue.paint.page_templates import available_template_names
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        for name in available_template_names():
            action = menu.addAction(
                lang.get(f"paint_pages_template_{name}", name),
            )
            action.triggered.connect(
                lambda _checked=False, n=name: self._add_page_from_template(n),
            )
        return menu

    def _on_row_changed(self, row: int) -> None:
        if self._suspend or row < 0:
            return
        project = self._project()
        if project is None or row >= project.page_count:
            return
        if project.active_page_index != row:
            project.active_page_index = row
            self.page_selected.emit(row)

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        """Double-click forces a swap to that page even if the row
        index didn't change (e.g. the user re-selected the active
        row to refresh)."""
        idx = int(item.data(Qt.ItemDataRole.UserRole))
        self.page_selected.emit(idx)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """Inline-rename on the page label edits the project's
        ``ProjectPage.name`` field."""
        if self._suspend:
            return
        project = self._project()
        if project is None:
            return
        idx = int(item.data(Qt.ItemDataRole.UserRole))
        if not (0 <= idx < project.page_count):
            return
        text = item.text()
        # Strip the ``"N. "`` prefix the row label adds back.
        prefix = f"{idx + 1}. "
        new_name = text[len(prefix):] if text.startswith(prefix) else text
        new_name = new_name.strip() or project.pages[idx].name
        project.pages[idx].name = new_name
        self.refresh()

    def _on_add(self) -> None:
        from Imervue.paint.document import PaintDocument
        from Imervue.paint.paint_project import ProjectPage
        project = self._project()
        if project is None:
            self._warn_no_project()
            return
        ref = project.active_page() or project.pages[0]
        h, w = ref.document.shape or (1024, 1024)
        # Match the active page's size + a fresh white background so
        # the new page slots into the same comic dimensions without
        # needing a template pick.
        arr = np.full((h, w, 4), 255, dtype=np.uint8)
        document = PaintDocument()
        document.load_image(arr)
        page = ProjectPage(
            document=document, name=f"Page {project.page_count + 1}",
        )
        project.add_page(page)
        self.refresh()

    def _on_remove(self) -> None:
        project = self._project()
        if project is None:
            return
        # remove_page refuses to drop the last page (returns False);
        # silently no-op so we don't block the UI with a modal — the
        # dock's row count makes the rejection self-evident.
        if not project.remove_page(project.active_page_index):
            return
        self.refresh()

    def _on_duplicate(self) -> None:
        project = self._project()
        if project is None:
            return
        active = project.active_page()
        if active is None:
            return
        from copy import deepcopy
        from Imervue.paint.paint_project import ProjectPage
        clone = ProjectPage(
            document=deepcopy(active.document),
            name=f"{active.name} copy",
        )
        project.add_page(clone)
        self.refresh()

    def _on_move(self, *, up: bool) -> None:
        project = self._project()
        if project is None:
            return
        src = project.active_page_index
        dst = src - 1 if up else src + 1
        if not (0 <= dst < project.page_count):
            return
        if project.move_page(src, dst):
            project.active_page_index = dst
            self.refresh()

    def _add_page_from_template(self, template_name: str) -> None:   # pragma: no cover - menu UI
        from Imervue.paint.page_templates import (
            make_blank_page,
            template_by_name,
        )
        project = self._project()
        if project is None:
            self._warn_no_project()
            return
        try:
            tpl = template_by_name(template_name)
        except KeyError:
            return
        # Prompt for a page name; default to the next sequential.
        lang = language_wrapper.language_word_dict
        default = f"Page {project.page_count + 1}"
        name, ok = QInputDialog.getText(
            self,
            lang.get("paint_pages_template_title", "Add page from template"),
            lang.get("paint_pages_template_label", "Page name:"),
            text=default,
        )
        if not ok or not name.strip():
            return
        page = make_blank_page(tpl, name=name.strip())
        project.add_page(page)
        self.refresh()

    def _warn_no_project(self) -> None:
        # Prefer the workspace's toast manager (non-blocking) so the
        # artist isn't forced to dismiss a modal just to learn that the
        # action requires a project. Fall back to QMessageBox for
        # legacy embedders that don't construct a toast surface.
        lang = language_wrapper.language_word_dict
        message = lang.get(
            "paint_pages_no_project_msg",
            "No project bound — start one via File ▸ New Project.",
        )
        toast = self._find_toast()
        if toast is not None:
            toast.info(message)
            return
        QMessageBox.information(
            self,
            lang.get("paint_pages_add_title", "Add page"),
            message,
        )

    def _find_toast(self):
        """Walk the parent chain looking for a workspace that owns a
        ``ToastManager`` so the warning surfaces non-blockingly. The
        page dock is created with the workspace as parent, but tests
        sometimes embed it under a bare QWidget — falling back to None
        keeps the QMessageBox path alive."""
        widget = self.parent()
        while widget is not None:
            toast = getattr(widget, "toast", None)
            if toast is not None:
                return toast
            widget = widget.parent() if hasattr(widget, "parent") else None
        return None


def _thumbnail_icon(page) -> QIcon:   # pragma: no cover - Qt icon
    """Build a 64-px thumbnail icon for a project page from its
    document's first composite. Falls back to a blank pixmap when
    the page hasn't been painted on yet."""
    composite = page.document.composite()
    if composite is None or composite.size == 0:
        return QIcon(QPixmap(PAGE_THUMB_PX, PAGE_THUMB_PX))
    h, w = composite.shape[:2]
    side = max(1, h, w)
    scale = PAGE_THUMB_PX / float(side)
    new_h = max(1, int(round(h * scale)))
    new_w = max(1, int(round(w * scale)))
    # Cheap nearest-neighbour resize via numpy slicing.
    ys = (np.arange(new_h, dtype=np.float32) * (h / new_h)).astype(np.int32)
    xs = (np.arange(new_w, dtype=np.float32) * (w / new_w)).astype(np.int32)
    thumb = np.ascontiguousarray(composite[ys][:, xs])
    qimg = QImage(
        thumb.data, new_w, new_h, new_w * 4, QImage.Format.Format_RGBA8888,
    ).copy()
    return QIcon(QPixmap.fromImage(qimg))
