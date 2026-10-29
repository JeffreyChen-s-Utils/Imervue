"""Workspace tabs of the main window.

Switching between the Imervue (browse), Modify and Paint tabs, handing the
viewer's current image to Paint, and routing Left / Right on the workspace tab
bar to image navigation. ``ImervueMainWindow`` mixes these methods in.
"""
from __future__ import annotations

import logging

from Imervue.image.read_errors import IMAGE_READ_ERRORS
from Imervue.multi_language.language_wrapper import language_wrapper

_logger = logging.getLogger("Imervue.main_window")


class MainWindowWorkspacesMixin:
    """Workspace tabs of the main window."""

    def _on_main_tab_changed(self, idx: int) -> None:
        """Switch between Imervue (viewer), Modify and Paint tabs."""
        self._build_optional_tab_on_open(idx)
        for shortcut in self._folder_tab_shortcuts:
            shortcut.setEnabled(idx == 0)
        if idx == 1:
            # 切到修改分頁 → 綁定圖片，canvas 會放進中央的 CanvasHost
            images = self.viewer.model.images
            path = None
            if images and 0 <= self.viewer.current_index < len(images):
                path = images[self.viewer.current_index]
            self.modify_panel.bind_to_path(path)
        elif idx == 2:
            # Opening the workspace must preserve its documents and undo stacks.
            _ = self.paint_workspace
        else:
            # 切回 Imervue 主頁
            self.exif_sidebar.update_info()

    def _bind_paint_workspace_to_current_image(self) -> None:
        """Decode the viewer's current image into a new Paint document and show it."""
        images = self.viewer.model.images
        if not images or not (0 <= self.viewer.current_index < len(images)):
            return
        path = images[self.viewer.current_index]
        try:
            # The viewer's decode: RAW developed, sRGB, upright. Pillow alone reads
            # a RAW's small embedded preview and ignores orientation and profile.
            from Imervue.gpu_image_view.images.image_loader import decode_image_file
            arr = decode_image_file(path)
        except IMAGE_READ_ERRORS as exc:
            _logger.exception("Could not open %s in Paint", path)
            self.toast.error(language_wrapper.language_word_dict.get(
                "annotation_load_failed", "Load failed: {error}",
            ).format(error=exc))
            return
        workspace = self.paint_workspace
        # load_image replaces the blank document; avoid a second full-size allocation.
        workspace.new_tab(width=1, height=1)
        workspace.load_image(arr, source_path=path)
        self._main_tabs.setCurrentIndex(2)

    def eventFilter(self, obj, event):
        """Route Left/Right on the Modify / Paint tab bars to image nav.

        On those tabs the default tab-switch is unwanted — the user wants the
        arrows to page images like the browse view. Every other tab / key
        falls through to Qt's default handling.
        """
        from PySide6.QtCore import QEvent, Qt
        if (obj is self._workspace_tab_bar
                and event.type() == QEvent.Type.KeyPress):
            from Imervue.gui.main_tab_nav import tab_arrow_action
            action = tab_arrow_action(
                self._main_tabs.currentIndex(), event.key(),
                Qt.Key.Key_Left, Qt.Key.Key_Right,
            )
            if action is not None:
                target, direction = action
                if target == "modify":
                    self.modify_panel.navigate_image(direction)
                else:
                    self._navigate_paint_image(direction)
                return True
        return super().eventFilter(obj, event)

    def _navigate_paint_image(self, direction: int) -> None:
        """Page the viewer's current image and open it in a new Paint document."""
        from Imervue.gpu_image_view.actions.select import (
            switch_to_next_image,
            switch_to_previous_image,
        )
        if direction > 0:
            switch_to_next_image(main_gui=self.viewer)
        else:
            switch_to_previous_image(main_gui=self.viewer)
        self._bind_paint_workspace_to_current_image()
