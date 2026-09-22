"""Mouse and wheel input of the viewer.

Wheel zoom (and Shift+wheel loupe magnification, grid scrolling, reading-mode
scrolling), press / drag / release for panning, selection and the minimap,
and double-click to toggle between the tile grid and deep zoom.
``GPUImageView`` mixes these methods in.
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from Imervue.gpu_image_view.minimap import point_in_rect
from Imervue.menu.right_click_menu import right_click_context_menu


class ViewMouseMixin:
    """Mouse and wheel input of the viewer."""

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if self.tile_grid_mode:
            # 滾輪 → 上下捲動縮圖列表
            scroll_amount = delta / 2  # angleDelta 通常 ±120，/2 → ±60 px
            self.grid_offset_y += scroll_amount
            self._clamp_grid_scroll()
            self.update()
            return
        if (self.deep_zoom and self._loupe_enabled
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            from Imervue.gpu_image_view.hud_geometry import (
                clamp_loupe_magnification,
            )
            self._loupe_magnification = clamp_loupe_magnification(
                self._loupe_magnification, delta)
            self.update()
            return
        if self.deep_zoom and self._reading_mode:
            self._browse.reading_wheel(delta)
            return
        if self.deep_zoom:
            self._input.handle_deep_zoom_wheel(event, delta)

    def _zoom_step(self, zoom_in: bool) -> None:
        """Keyboard zoom in/out — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        self._input.zoom_step(zoom_in)

    def _fit_window_with_toast(self) -> None:
        """Fit-to-window + toast — called by the key-action dispatcher.
        External contract, keep the name/signature stable."""
        if self.deep_zoom:
            self._fit_to_window()
            self.update()
            self._toast("fit_window", "Fit to Window")

    def mousePressEvent(self, event):
        self.last_pos = event.position()
        self._cancel_hover_preview()
        # 任何按下都中止進行中的平滑動畫，使用者重新取得控制權。
        self._zoom_ease.stop()
        self._pan_momentum.stop()

        # ===== 中鍵拖動 =====
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = True
            self._last_pan_velocity = (0.0, 0.0)
            return

        # ===== 右鍵 → 顯示選單 =====
        if event.button() == Qt.MouseButton.RightButton:
            right_click_context_menu(
                main_gui=self,
                global_pos=event.globalPosition().toPoint(),
                local_pos=event.position()
            )
            return

        # ===== 左鍵 =====
        if event.button() == Qt.MouseButton.LeftButton:
            if self.tile_grid_mode:
                # 改用滑鼠操作 → 收起鍵盤焦點框
                self.focus_ring_visible = False
                self._drag_start_pos = event.position()
                self._drag_end_pos = event.position()
                self._drag_selecting = False  # 先不啟動，等拖動才算框選
            elif self.deep_zoom:
                if self._browse.handle_deep_zoom_press(event.position()):
                    return
                self._input.begin_zoom_band(event.position())
            return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Deep zoom: double-click toggles fit ↔ 100% centred on the cursor,
        # except inside the minimap (which owns clicks for navigation).
        if (event.button() == Qt.MouseButton.LeftButton
                and self.deep_zoom and not self.tile_grid_mode):
            pos = event.position()
            rect = self._current_minimap_rect()
            if rect is None or not point_in_rect(pos.x(), pos.y(), rect):
                self._input.toggle_zoom_at(pos)
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        self._input.update_hover_state(event)

        if self.last_pos is None:
            self.last_pos = event.position()
            return

        delta = event.position() - self.last_pos
        self.last_pos = event.position()

        if self._middle_dragging:
            self._input.handle_middle_drag(delta)
            return

        if self._minimap_dragging:
            self._input.minimap_nav_to(event.position())
            return

        if self._zoom_band_active:
            self._input.update_zoom_band(event)
            return

        self._input.handle_left_drag_select(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = False
            self._input.start_pan_momentum()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._minimap_dragging:
            self._minimap_dragging = False
            return
        if (event.button() == Qt.MouseButton.LeftButton
                and self._zoom_band_active):
            self._input.finish_zoom_band(event.position())
            return
        if (
            self.tile_grid_mode
            and event.button() == Qt.MouseButton.LeftButton
            and self._input.handle_tile_release(event)
        ):
            return
        super().mouseReleaseEvent(event)
