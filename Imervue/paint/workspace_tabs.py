"""Multi-document tab management for the Paint workspace.

Extracted from :mod:`paint_workspace`: per-tab dirty tracking, the new /
close / cycle tab commands, unsaved-work prompts, and tab title / tooltip
maintenance. Composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace` via
:class:`TabManagerMixin`.
"""
from __future__ import annotations

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.canvas import PaintCanvas


class TabManagerMixin:
    """Tab strip behaviour: dirty flags, open / close / cycle, prompts.

    Expects the host to provide ``_tabs`` (QTabWidget), ``_tab_dirty``
    (dict), ``_canvas``, ``_dispatcher``, ``toast`` and a
    ``_file_menu_bridge`` slot.
    """

    def _has_unsaved_tabs(self) -> bool:
        """Return True if any of the open tabs has the dirty flag set.

        Iterates over the live ``_tab_dirty`` map rather than the
        QTabWidget so a stale entry that was never cleaned up doesn't
        accidentally claim an unsaved tab. Closed tabs are popped from
        the map at close time, so anything in here is real.
        """
        return any(self._tab_dirty.get(w, False) for w in self._tab_dirty)

    def _unsaved_tab_titles(self) -> list[str]:
        """Return the titles of every tab carrying unsaved edits.

        Pulled out of the close prompt so a future "save all" command
        can surface the same list without re-walking the dirty map.
        """
        names: list[str] = []
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            if not self._tab_dirty.get(widget, False):
                continue
            names.append(self._tabs.tabText(i).rstrip(" *"))
        return names

    def _confirm_discard_all_unsaved(self) -> bool:
        """Prompt the user before tearing down a window with dirty tabs.

        Returns ``True`` for "Discard all" or "Save…"-then-clean,
        ``False`` for cancel. Lists the titles inline so the user
        can see exactly which tabs are about to be lost.
        """
        from PySide6.QtWidgets import QMessageBox
        lang = language_wrapper.language_word_dict
        names = self._unsaved_tab_titles()
        box = QMessageBox(self)
        box.setWindowTitle(lang.get(
            "paint_close_window_unsaved_title",
            "Close with unsaved changes?",
        ))
        box.setText(lang.get(
            "paint_close_window_unsaved_body",
            "{count} tab(s) with unsaved edits:\n• {names}",
        ).format(count=len(names), names="\n• ".join(names)))
        box.setIcon(QMessageBox.Icon.Warning)
        save = box.addButton(
            lang.get("paint_close_window_save_active", "Save active…"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard = box.addButton(
            lang.get("paint_close_window_discard_all", "Discard all"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self._save_active_then_close(lang)
        return clicked is discard

    def _save_active_then_close(self, lang: dict) -> bool:
        """Export the active tab, then report whether the window may close.

        Returns ``True`` only when no dirty tabs remain after the
        export. Surfaces a toast when the close is aborted so the user
        knows the action wasn't silently eaten.
        """
        bridge = getattr(self, "_file_menu_bridge", None)
        if bridge is not None and hasattr(bridge, "export_active_image"):
            bridge.export_active_image()
        still_dirty = self._has_unsaved_tabs()
        if still_dirty:
            toast = getattr(self, "toast", None)
            if toast is not None:
                toast.warning(lang.get(
                    "paint_close_still_dirty",
                    "Close cancelled — some tabs are still unsaved",
                ))
        return not still_dirty

    def tab_count(self) -> int:
        """Return how many open documents the workspace currently holds."""
        return self._tabs.count()

    def new_tab(self) -> PaintCanvas:
        """Open a fresh blank document in a new tab and switch to it.

        Returns the new tab's :class:`PaintCanvas` so callers can
        e.g. ``load_image`` into it. The dispatcher follows because
        its providers read from ``self._canvas`` at event time.
        """
        canvas = PaintCanvas(self)
        canvas.new_blank_document()
        canvas.set_tool_dispatcher(self._dispatcher)
        idx = self._tabs.addTab(canvas, self._next_untitled_tab_name())
        self._tabs.setCurrentIndex(idx)
        return canvas

    def close_tab(self, index: int, *, force: bool = False) -> bool:
        """Close the tab at ``index``. Returns ``True`` on success.

        Refuses to close the last remaining tab — the workspace
        always needs at least one paintable canvas, mirroring the
        single-tab invariant from before tabs existed. ``force=True``
        bypasses the unsaved-work prompt; the tabCloseRequested
        handler uses it after the user explicitly confirms discard.
        """
        if index < 0 or index >= self._tabs.count():
            return False
        if self._tabs.count() <= 1:
            return False
        widget = self._tabs.widget(index)
        needs_prompt = (
            not force and self._tab_dirty.get(widget, False)
        )
        if needs_prompt and not self._confirm_discard_unsaved(widget):
            return False
        self._tab_dirty.pop(widget, None)
        self._tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        return True

    def _confirm_discard_unsaved(self, widget) -> bool:
        """Prompt the user before closing a tab with unsaved edits.

        Returns ``True`` when the user picks "Discard"; ``False``
        when they cancel. ``Save`` is offered as a third option that
        triggers the active export and re-checks the dirty flag.
        """
        from PySide6.QtWidgets import QMessageBox
        lang = language_wrapper.language_word_dict
        box = QMessageBox(self)
        box.setWindowTitle(lang.get(
            "paint_close_unsaved_title", "Close tab with unsaved changes?",
        ))
        box.setText(lang.get(
            "paint_close_unsaved_body",
            "This tab has unsaved edits. Close anyway?",
        ))
        box.setIcon(QMessageBox.Icon.Question)
        save = box.addButton(
            lang.get("paint_close_unsaved_save", "Save…"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard = box.addButton(
            lang.get("paint_close_unsaved_discard", "Discard"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            bridge = getattr(self, "_file_menu_bridge", None)
            if bridge is not None and hasattr(bridge, "export_active_image"):
                bridge.export_active_image()
            return not self._tab_dirty.get(widget, False)
        return clicked is discard

    def _next_untitled_tab_name(self) -> str:
        """Generate a unique 'Untitled-N' name for a new tab."""
        existing = {
            self._tabs.tabText(i).rstrip(" *")
            for i in range(self._tabs.count())
        }
        n = self._tabs.count() + 1
        while f"Untitled-{n}" in existing:
            n += 1
        return f"Untitled-{n}"

    def _on_tab_close_requested(self, index: int) -> None:
        self.close_tab(index)

    def _set_tab_dirty(self, canvas, dirty: bool) -> None:
        """Update the per-tab modified flag + tab title.

        Tab titles end with a trailing ``" *"`` while dirty so the
        user sees at a glance which tabs carry unsaved edits. The
        flag map is keyed by the canvas widget itself so closing a
        tab cleans up the entry without leaking references.
        """
        if canvas is None:
            return
        prev = self._tab_dirty.get(canvas, False)
        if prev == dirty:
            return
        self._tab_dirty[canvas] = dirty
        self._refresh_tab_title(canvas)

    def _refresh_tab_title(self, canvas) -> None:
        index = self._tabs.indexOf(canvas)
        if index < 0:
            return
        base = self._tabs.tabText(index).rstrip(" *")
        suffix = " *" if self._tab_dirty.get(canvas, False) else ""
        self._tabs.setTabText(index, f"{base}{suffix}")
        self._refresh_tab_tooltip(canvas, base)

    def _refresh_tab_tooltip(self, canvas, base_title: str) -> None:
        """Populate the per-tab hover tooltip with the full title +
        canvas dimensions + dirty state.

        Tab text gets truncated by Qt when the bar is full; the
        tooltip is the only place we can guarantee the full label
        is reachable. We also surface size / modified state so a
        user with several tabs can compare at a glance which one
        is the WIP.
        """
        index = self._tabs.indexOf(canvas)
        if index < 0:
            return
        lang = language_wrapper.language_word_dict
        lines: list[str] = [base_title]
        document = (
            canvas.document() if hasattr(canvas, "document") else None
        )
        shape = getattr(document, "shape", None) if document is not None else None
        if shape is not None:
            h, w = shape
            lines.append(
                lang.get("paint_tab_tooltip_size", "{w}×{h}").format(w=w, h=h),
            )
        if self._tab_dirty.get(canvas, False):
            lines.append(
                lang.get("paint_tab_tooltip_modified", "Modified — unsaved"),
            )
        self._tabs.setTabToolTip(index, "\n".join(lines))

    def mark_active_tab_clean(self) -> None:
        """Public hook called by file-menu save / export actions."""
        self._set_tab_dirty(self._canvas, False)

    def _on_tab_changed(self, index: int) -> None:
        """Reassign ``self._canvas`` to the new active tab and rebind
        the docks + signal connections that depend on it."""
        if index < 0:
            return
        new_canvas = self._tabs.widget(index)
        if not isinstance(new_canvas, PaintCanvas):
            return
        self._rebind_canvas_signals(self._canvas, new_canvas)
        self._canvas = new_canvas
        self._canvas.set_tool_dispatcher(self._dispatcher)
        if hasattr(self, "_layer_dock"):
            self._layer_dock.set_document(self._canvas.document())
        if hasattr(self, "_navigator_dock"):
            self._navigator_dock.set_zoom(self._canvas.zoom_factor())
        self._refresh_navigator_preview()

    def _rebind_canvas_signals(self, old_canvas, new_canvas) -> None:
        """Move the per-canvas hover / zoom / document hooks from the
        outgoing tab to the incoming one."""
        if old_canvas is not None and old_canvas is not new_canvas:
            try:
                old_canvas.hover_changed.disconnect(self._on_hover_changed)
                old_canvas.image_loaded.disconnect(self._on_image_loaded)
                old_canvas.zoom_changed.disconnect(self._navigator_dock.set_zoom)
                old_canvas.zoom_changed.disconnect(self._on_zoom_changed_refresh_cursor)
                old_canvas.document_changed.disconnect(self._on_document_changed)
            except (RuntimeError, TypeError):
                # Signal might already be disconnected (e.g. on shutdown).
                pass
        new_canvas.hover_changed.connect(self._on_hover_changed)
        new_canvas.image_loaded.connect(self._on_image_loaded)
        new_canvas.zoom_changed.connect(self._navigator_dock.set_zoom)
        new_canvas.zoom_changed.connect(self._on_zoom_changed_refresh_cursor)
        new_canvas.document_changed.connect(self._on_document_changed)

    def cycle_active_tab(self, direction: int) -> int:
        """Step the active paint tab by ``direction`` (+1 / -1).

        Wraps around at both ends — the workspace has a small,
        bounded set of tabs and wrapping is the friendlier behaviour
        when keyboard-cycling.
        """
        count = self._tabs.count()
        if count <= 1:
            return self._tabs.currentIndex()
        new_index = (self._tabs.currentIndex() + int(direction)) % count
        self._tabs.setCurrentIndex(new_index)
        return new_index
