"""Dual view, multi-monitor window and theater mode of the main window.

``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations

from Imervue.multi_language.language_wrapper import language_wrapper


class MainWindowViewsMixin:
    """Dual view, multi-monitor window and theater mode."""

    def activate_dual_view(self, mode: str = "split") -> None:
        """Swap to the dual-image view.

        ``mode`` is one of ``"split"``, ``"manga"``, ``"manga_rtl"``. The
        pair is derived from ``viewer.current_index``: for split we pair it
        with the NEXT image; for manga we do the same but step by 2 on arrows.
        """
        images = self.viewer.model.images
        if not images:
            return

        idx = self.viewer.current_index
        if idx < 0 or idx >= len(images):
            idx = 0
            self.viewer.current_index = 0

        right_idx = idx + 1 if idx + 1 < len(images) else None
        self.dual_view.set_mode(mode)
        self.dual_view.set_pair(
            images[idx],
            images[right_idx] if right_idx is not None else None,
        )

        if not self._dual_active:
            self._pre_dual_mode = self._browse_mode
            self._dual_active = True
        self._view_stack.setCurrentIndex(2)
        self.dual_view.setFocus()

    def deactivate_dual_view(self) -> None:
        if not self._dual_active:
            return
        self._dual_active = False
        # Restore to whichever browse mode was active before dual
        if self._pre_dual_mode == "list":
            self._view_stack.setCurrentIndex(1)
        else:
            self._view_stack.setCurrentIndex(0)

    def _on_dual_closed(self) -> None:
        self.deactivate_dual_view()

    def _ensure_multi_monitor(self):
        ctrl = getattr(self, "_multi_monitor", None)
        if ctrl is None:
            from Imervue.gui.multi_monitor_window import MultiMonitorController
            ctrl = MultiMonitorController(self)
            self._multi_monitor = ctrl
        return ctrl

    def toggle_multi_monitor_window(self) -> None:
        self._ensure_multi_monitor().toggle()

    def is_theater_mode(self) -> bool:
        return bool(getattr(self, "_theater_mode", False))

    def toggle_theater_mode(self) -> None:
        """Hide all chrome (menu / status / tree / tabs / sidebar) to focus on the image.

        Unlike fullscreen, the window stays in its current decoration — theater
        just collapses the surrounding UI. Toggling again restores everything
        to its prior state.
        """
        now_theater = not self.is_theater_mode()
        self._theater_mode = now_theater
        widgets_to_hide = self._theater_widget_list()
        if now_theater:
            self._enter_theater_mode(widgets_to_hide)
        else:
            self._exit_theater_mode(widgets_to_hide)

    def _theater_widget_list(self) -> list:
        widgets = [
            self.menuBar(),
            self.statusBar(),
            getattr(self, "_tree_panel", self.tree),
            self._tab_bar,
            self.filename_label,
        ]
        sidebar = getattr(self, "exif_sidebar", None)
        if sidebar is not None:
            widgets.append(sidebar)
        main_tab_bar = self._main_tabs.tabBar()
        if main_tab_bar is not None:
            widgets.append(main_tab_bar)
        return widgets

    def _enter_theater_mode(self, widgets: list) -> None:
        self._theater_prev_visibility = [w.isVisible() for w in widgets]
        self._theater_widgets = widgets
        for w in widgets:
            w.setVisible(False)
        self._theater_toast("theater_on", "Theater mode — Shift+Tab to exit")

    def _exit_theater_mode(self, fallback_widgets: list) -> None:
        prev = getattr(self, "_theater_prev_visibility", None)
        widgets = getattr(self, "_theater_widgets", fallback_widgets)
        if prev and len(prev) == len(widgets):
            for w, vis in zip(widgets, prev, strict=False):
                w.setVisible(vis)
        else:
            for w in widgets:
                w.setVisible(True)
        self._theater_prev_visibility = None
        self._theater_widgets = None
        self._theater_toast("theater_off", "Theater mode off")

    def _theater_toast(self, key: str, default: str) -> None:
        if not hasattr(self, "toast"):
            return
        lang = language_wrapper.language_word_dict
        self.toast.info(lang.get(key, default))
