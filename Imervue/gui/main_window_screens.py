"""Window geometry and screen changes of the main window.

Saving and restoring the window geometry on a screen that still exists,
rescaling the window when it moves between monitors with different scale
factors, and re-fitting the viewer and the Modify canvas after a move or
resize. ``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations

import contextlib

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication

from Imervue.system.qt_timers import call_later
from Imervue.user_settings.user_setting_dict import user_setting_dict
from Imervue.system.best_effort import best_effort


class MainWindowScreensMixin:
    """Window geometry and screen changes of the main window."""

    def moveEvent(self, event):  # noqa: N802 — Qt naming
        super().moveEvent(event)
        # __init__ 還沒跑完前 Qt 就可能送出第一個 moveEvent。
        timer = getattr(self, "_screen_adapt_timer", None)
        if timer is not None:
            timer.start()

    def resizeEvent(self, event):  # noqa: N802 — Qt naming
        super().resizeEvent(event)
        self._reflow_modify_canvas()

    def _reflow_modify_canvas(self) -> None:
        """Re-flow the Modify splitter and re-fit its canvas after a window /
        screen size change.

        The splitter holds absolute pane sizes, so without this the centre
        canvas kept its old width when the window shrank and the image
        overflowed / was cropped. Only the Modify canvas is touched — NOT the
        deep-zoom viewer, whose user zoom must survive a plain window resize.
        """
        if getattr(self, "_main_tabs", None) is None:
            return
        from Imervue.gui.main_tab_nav import should_refit_modify_canvas
        canvas = getattr(getattr(self, "modify_panel", None), "_canvas", None)
        if should_refit_modify_canvas(
                self._main_tabs.currentIndex(), canvas is not None):
            splitter = getattr(self, "_modify_splitter", None)
            if splitter is not None:
                self.modify_panel._size_modify_splitter(splitter, _retries=0)
            canvas.update()

    def _connect_screen_change_signal(self, _retries: int = 20) -> None:
        """Subscribe to the window's screen-changed signal exactly once.

        ``windowHandle()`` can still be None on the first deferred attempt (the
        native window isn't created until the widget is shown). A one-shot that
        gave up then left the signal permanently unconnected, so a later
        drag/restore to another monitor never re-fit the view. Retry on a short
        timer until the handle exists (bounded).
        """
        if self._screen_signal_connected:
            return
        handle = self.windowHandle()
        if handle is None:
            if _retries > 0:
                call_later(50, self, lambda: self._connect_screen_change_signal(_retries - 1))
            return
        handle.screenChanged.connect(self._on_screen_changed)
        self._screen_signal_connected = True

    def _on_screen_changed(self, _screen) -> None:
        """The window moved to a different physical screen — re-fit the view.

        Fires for the startup jump from the primary screen to the restored
        screen too, so the first display no longer keeps the primary screen's
        size / DPI. The frame rescale stays with the debounced ``moveEvent``
        path; here we only re-fit what's shown.
        """
        self._refit_current_view_for_screen()

    def _refit_current_view_for_screen(self) -> None:
        """Re-fit the deep-zoom viewer and, if active, the Modify canvas."""
        from Imervue.gui.main_tab_nav import should_refit_modify_canvas
        self._refit_deep_zoom_image()
        canvas = getattr(self.modify_panel, "_canvas", None)
        if should_refit_modify_canvas(
                self._main_tabs.currentIndex(), canvas is not None):
            splitter = getattr(self, "_modify_splitter", None)
            if splitter is not None:
                # Two chains, as on the deep-zoom path: the first drains Qt's
                # queued layout, the second spans the window actually landing on
                # the new monitor. setSizes has no per-paint net behind it, so
                # without the second an intermediate width is locked in.
                self.modify_panel._size_modify_splitter(splitter)
                self.modify_panel.schedule_modify_splitter_settle(splitter)
            call_later(0, canvas, canvas.update)

    def _adapt_to_current_screen(self) -> None:
        """Debounced ``moveEvent`` handler.

        When the window settles on a screen with a different available
        geometry (dragged to another monitor, or the monitor changed
        resolution), rescale the frame to keep its relative footprint and
        re-fit the current view so the whole picture stays visible.
        """
        screen = self.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        new_avail = (avail.x(), avail.y(), avail.width(), avail.height())
        old_avail, self._last_screen_avail = self._last_screen_avail, new_avail
        if old_avail is None or old_avail == new_avail:
            return
        # 最大化 / 全螢幕視窗由 OS 自己重排到新螢幕，只需重新 fit 圖片。
        if not (self.isMaximized() or self.isFullScreen()):
            self._rescale_window_between_screens(old_avail, new_avail)
        self._refit_current_view_for_screen()

    def _rescale_window_between_screens(self, old_avail, new_avail) -> None:
        """Keep the window's relative size / position on the new screen."""
        from Imervue.gui.screen_fit import rescale_rect_between_screens
        frame = self.frameGeometry()
        client = self.geometry()
        frame_rect = (frame.x(), frame.y(), frame.width(), frame.height())
        target = rescale_rect_between_screens(frame_rect, old_avail, new_avail)
        if target == frame_rect:
            return
        # setGeometry 吃的是 CLIENT rect — 把 frame 目標往內縮掉視窗
        # 裝飾邊距，標題列才不會被擠出螢幕外。
        left = client.x() - frame.x()
        top = client.y() - frame.y()
        extra_w = frame.width() - client.width()
        extra_h = frame.height() - client.height()
        x, y, w, h = target
        self.setGeometry(
            x + left, y + top,
            max(1, w - extra_w), max(1, h - extra_h),
        )

    def _refit_deep_zoom_image(self) -> None:
        """Fit the whole deep-zoom image into the (possibly resized) canvas.

        The viewer owns the timing: the fit is deferred until its canvas size
        settles after the ``setGeometry`` layout pass, and parked until the
        viewer is visible again when the screen changed while another main tab
        was in front. Intentionally overrides a user zoom/pan — landing on a
        new screen means "show me the whole image at this screen's size".
        """
        self.viewer.request_screen_refit()

    def _save_window_geometry(self) -> None:
        """Save window geometry + state into user_setting_dict."""
        import base64
        with best_effort("store the window geometry"):
            user_setting_dict["window_geometry"] = base64.b64encode(
                bytes(self.saveGeometry())
            ).decode("ascii")
            user_setting_dict["window_state"] = base64.b64encode(
                bytes(self.saveState())
            ).decode("ascii")
            user_setting_dict["window_maximized"] = self.isMaximized()

    def _restore_window_geometry(self) -> None:
        """Restore saved geometry if it lands on a visible screen, else showMaximized."""
        import base64
        geo_b64 = user_setting_dict.get("window_geometry", "")
        if not geo_b64:
            self.showMaximized()
            return

        try:
            geo = QByteArray(base64.b64decode(geo_b64))
            self.restoreGeometry(geo)
        except (ValueError, TypeError):
            # Not base64 (binascii.Error is a ValueError) or not a string at all.
            self.showMaximized()
            return

        # 還原 state（工具列、dock 等）
        state_b64 = user_setting_dict.get("window_state", "")
        if state_b64:
            with contextlib.suppress(ValueError, TypeError):
                self.restoreState(QByteArray(base64.b64decode(state_b64)))

        # 確認還原後的視窗中心仍在某個可用螢幕內。若先前的副螢幕被拔除、
        # 視窗座標落在不可見區域，則改用 showMaximized 救回。
        if not self._geometry_on_visible_screen():
            self.showMaximized()
            return

        # 還原最大化狀態
        if user_setting_dict.get("window_maximized", True):
            self.showMaximized()
        else:
            self.showNormal()

    def _geometry_on_visible_screen(self) -> bool:
        """Check if the window's center point lands on any available screen."""
        center = self.frameGeometry().center()
        return any(
            screen.availableGeometry().contains(center)
            for screen in QApplication.screens()
        )
