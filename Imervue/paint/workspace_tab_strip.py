"""Canvas tab-strip affordances for the Paint workspace.

Split out of :mod:`paint_workspace` to keep the coordinator small.
:class:`TabStripMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace` ahead of
``QMainWindow``, so its ``eventFilter`` is the one Qt calls for the canvas
tab bar and the canvas; unhandled events continue to the Qt base filter.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.multi_language.language_wrapper import language_wrapper


class TabStripMixin:
    """The "+" corner button and the tab-bar / canvas event filter.

    Expects the host to provide ``_tabs``, ``_canvas_tab_bar``, ``_canvas``,
    ``new_tab``, ``close_tab`` and (optionally) ``_welcome_hint``.
    """

    def _install_new_tab_corner_button(self) -> None:
        """Mount a small "+" button in the tab strip's right corner so
        the artist has a one-click affordance for ``new_tab``."""
        from PySide6.QtWidgets import QToolButton
        lang = language_wrapper.language_word_dict
        self._new_tab_btn = QToolButton(self._tabs)
        self._new_tab_btn.setText("+")
        self._new_tab_btn.setAutoRaise(True)
        self._new_tab_btn.setToolTip(
            lang.get("paint_tab_new_tooltip", "New tab (Ctrl+T)"),
        )
        self._new_tab_btn.clicked.connect(self.new_tab)
        self._tabs.setCornerWidget(self._new_tab_btn, Qt.Corner.TopRightCorner)

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if (
            hasattr(self, "_welcome_hint")
            and obj is self._canvas
            and event.type() == event.Type.Resize
            and self._welcome_hint.isVisible()
        ):
            self._welcome_hint.position_centred(
                self._canvas.width(), self._canvas.height(),
            )
        if obj is self._canvas_tab_bar and self._handle_tab_bar_event(event):
            return True
        return super().eventFilter(obj, event)

    def _handle_tab_bar_event(self, event) -> bool:
        """Forward middle-click on the tab bar to ``close_tab``.

        Returns ``True`` when the event is consumed so Qt doesn't also
        dispatch it as a tab activate.
        """
        if event.type() != event.Type.MouseButtonRelease:
            return False
        if event.button() != Qt.MouseButton.MiddleButton:
            return False
        pos = event.position() if hasattr(event, "position") else event.pos()
        index = self._canvas_tab_bar.tabAt(pos.toPoint())
        if index < 0:
            return False
        self.close_tab(index)
        return True
