"""Canvas right-click quick-actions menu for the Paint workspace.

Split out of :mod:`paint_workspace` to keep the coordinator small.
:class:`CanvasMenuMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace`.
"""
from __future__ import annotations

import numpy as np

from Imervue.multi_language.language_wrapper import language_wrapper


class CanvasMenuMixin:
    """Builds the canvas context menu and its selection helpers.

    Expects the host to provide ``_canvas``, ``_undo_stack``, ``undo`` and
    ``redo``.
    """

    def _show_canvas_context_menu(self, pos) -> None:
        """Pop a raster-editor quick-actions menu at the right-click
        position. Construction is delegated to
        :meth:`_build_canvas_context_menu` so tests can verify the action
        set without driving Qt's modal loop."""
        menu = self._build_canvas_context_menu()
        menu.exec(self._canvas.mapToGlobal(pos))

    def _build_canvas_context_menu(self):
        """Return the QMenu that ``_show_canvas_context_menu`` pops.

        Surfaces the keyboard-frequent actions (undo / redo / select all
        / deselect / fit / 100 %). Each entry is wired to the same
        workspace methods the menu / shortcut invokes.
        """
        from PySide6.QtWidgets import QMenu
        lang = language_wrapper.language_word_dict
        menu = QMenu(self._canvas)
        undo_action = menu.addAction(lang.get("paint_edit_undo", "Undo"))
        undo_action.triggered.connect(self.undo)
        undo_action.setEnabled(self._undo_stack.can_undo())
        redo_action = menu.addAction(lang.get("paint_edit_redo", "Redo"))
        redo_action.triggered.connect(self.redo)
        redo_action.setEnabled(self._undo_stack.can_redo())
        menu.addSeparator()
        select_all = menu.addAction(
            lang.get("paint_edit_select_all", "Select All"),
        )
        select_all.triggered.connect(self._select_all_canvas)
        deselect = menu.addAction(
            lang.get("paint_edit_deselect", "Deselect"),
        )
        deselect.triggered.connect(self._deselect_canvas)
        deselect.setEnabled(self._has_active_selection())
        menu.addSeparator()
        fit = menu.addAction(lang.get("paint_view_fit", "Fit to Window"))
        fit.triggered.connect(self._canvas.reset_view)
        zoom_100 = menu.addAction(lang.get("paint_view_100", "100 %"))
        zoom_100.triggered.connect(lambda: self._canvas.set_zoom(1.0))
        return menu

    def _select_all_canvas(self) -> None:
        document = self._canvas.document()
        shape = getattr(document, "shape", None)
        if shape is None:
            return
        h, w = shape
        mask = np.ones((h, w), dtype=bool)
        if hasattr(document, "set_selection"):
            document.set_selection(mask)
            self._canvas.update()

    def _deselect_canvas(self) -> None:
        document = self._canvas.document()
        if hasattr(document, "set_selection"):
            document.set_selection(None)
            self._canvas.update()

    def _has_active_selection(self) -> bool:
        document = self._canvas.document()
        if not hasattr(document, "selection"):
            return False
        sel = document.selection()
        return sel is not None and bool(sel.any())
