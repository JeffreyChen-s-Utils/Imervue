from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QFileDialog

from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.menu.recent_menu import rebuild_recent_menu, build_recent_menu
from Imervue.user_settings.recent_image import add_recent_folder, add_recent_image
from Imervue.user_settings.user_setting_dict import user_setting_dict

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

from Imervue.multi_language.language_wrapper import language_wrapper


def build_file_menu(ui_we_want_to_set: ImervueMainWindow):
    lang = language_wrapper.language_word_dict
    # ===== 檔案 =====
    file_menu = ui_we_want_to_set.menuBar().addMenu(lang.get("main_window_current_file"))

    # 新視窗
    new_window_action = file_menu.addAction(lang.get("menu_new_window", "New Window"))
    new_window_action.triggered.connect(lambda: _open_new_window(ui_we_want_to_set))

    file_menu.addSeparator()

    open_image_action = file_menu.addAction(lang.get("main_window_open_image"))
    open_image_action.triggered.connect(
        lambda: open_image(ui_we_want_to_set)
    )

    open_folder_action = file_menu.addAction(lang.get("main_window_open_folder"))
    open_folder_action.triggered.connect(lambda: open_folder(ui_we_want_to_set))

    build_recent_menu(ui_we_want_to_set=ui_we_want_to_set, menu=file_menu)

    # 書籤管理
    bookmark_action = file_menu.addAction(lang.get("bookmark_title", "Bookmarks"))
    bookmark_action.triggered.connect(lambda: _open_bookmarks(ui_we_want_to_set))

    # 標籤與相簿管理
    tag_album_action = file_menu.addAction(lang.get("tag_album_title", "Tags & Albums"))
    tag_album_action.triggered.connect(lambda: _open_tag_album(ui_we_want_to_set))

    file_menu.addSeparator()

    # 新增刪除動作
    delete_action = file_menu.addAction(lang.get("main_window_remove_undo_stack"))
    delete_action.triggered.connect(lambda: commit_pending_deletions(ui_we_want_to_set.viewer))

    file_menu.addSeparator()

    # 剪貼簿 → 註解
    paste_action = file_menu.addAction(
        lang.get("file_menu_paste_clipboard", "Paste from Clipboard")
    )
    paste_action.triggered.connect(lambda: _paste_from_clipboard(ui_we_want_to_set))

    monitor_action = file_menu.addAction(
        lang.get("file_menu_clipboard_monitor", "Auto-annotate Clipboard Images")
    )
    monitor_action.setCheckable(True)
    if hasattr(ui_we_want_to_set, "clipboard_monitor") \
            and ui_we_want_to_set.clipboard_monitor is not None:
        monitor_action.setChecked(ui_we_want_to_set.clipboard_monitor.is_enabled())
    monitor_action.toggled.connect(
        lambda checked: _toggle_clipboard_monitor(ui_we_want_to_set, checked)
    )

    file_menu.addSeparator()

    # 檔案關聯（僅 Windows）
    import sys
    if sys.platform == "win32":
        assoc_menu = file_menu.addMenu(lang.get("file_assoc_menu", "File Association"))
        reg_action = assoc_menu.addAction(lang.get("file_assoc_register", "Register 'Open with Imervue'"))
        reg_action.triggered.connect(lambda: _register_assoc(ui_we_want_to_set))
        unreg_action = assoc_menu.addAction(lang.get("file_assoc_unregister", "Remove file association"))
        unreg_action.triggered.connect(lambda: _unregister_assoc(ui_we_want_to_set))

    file_menu.addSeparator()

    exit_action = file_menu.addAction(lang.get("main_window_exit"))
    exit_action.triggered.connect(ui_we_want_to_set.close)

    # ===== Tile Size 選單 =====
    view_menu = ui_we_want_to_set.menuBar().addMenu(language_wrapper.language_word_dict.get("main_window_tile_size"))

    tile_group = QActionGroup(ui_we_want_to_set)
    tile_group.setExclusive(True)

    thumbnail_size = [128, 256, 512, 1024, "None"]

    for size in thumbnail_size:
        if size != "None":
            action = view_menu.addAction(f"{size} x {size}")
        else:
            action = view_menu.addAction(size)
        action.setCheckable(True)

        if size == ui_we_want_to_set.viewer.thumbnail_size:
            action.setChecked(True)

        tile_group.addAction(action)

        action.triggered.connect(
            lambda checked, s=size: ui_we_want_to_set.change_tile_size(s)
        )
    return file_menu


# ==========================
# 開啟資料夾
# ==========================
def open_folder(ui_we_want_to_set: ImervueMainWindow):
    folder = QFileDialog.getExistingDirectory(
        ui_we_want_to_set, language_wrapper.language_word_dict.get("main_window_select_folder"))

    if folder:
        ui_we_want_to_set.model.setRootPath(folder)
        ui_we_want_to_set.tree.setRootIndex(ui_we_want_to_set.model.index(folder))
        ui_we_want_to_set.viewer.clear_tile_grid()
        open_path(main_gui=ui_we_want_to_set.viewer, path=folder)

        ui_we_want_to_set.filename_label.setText(
            language_wrapper.language_word_dict.get(
                "main_window_current_folder_format"
            ).format(path=folder)
        )

        add_recent_folder(folder)
        rebuild_recent_menu(ui_we_want_to_set)
        user_setting_dict["user_last_folder"] = folder

# ==========================
# 開啟單張圖片
# ==========================
def open_image(ui_we_want_to_set: ImervueMainWindow):
    file_path, _ = QFileDialog.getOpenFileName(
        ui_we_want_to_set,
        language_wrapper.language_word_dict.get("main_window_select_image"),
        "",
        "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp *.gif *.apng *.svg *.cr2 *.nef *.arw *.dng *.raf *.orf)"
    )

    if not file_path:
        return

    # 使用統一路徑開啟流程（非同步載入）
    ui_we_want_to_set.viewer.clear_tile_grid()
    open_path(main_gui=ui_we_want_to_set.viewer, path=file_path)

    add_recent_image(file_path)
    rebuild_recent_menu(ui_we_want_to_set)
    user_setting_dict["user_last_folder"] = str(Path(file_path).parent)


# ==========================
# 新視窗
# ==========================
# 保持全域引用防止被 GC 回收
_extra_windows: list = []


def _open_new_window(parent: ImervueMainWindow):
    from Imervue.Imervue_main_window import ImervueMainWindow as MW
    win = MW()
    # 新視窗在跟 parent 同一個螢幕上開啟，稍微偏移避免完全重疊
    screen = parent.screen()
    if screen is not None:
        avail = screen.availableGeometry()
        w = int(avail.width() * 0.85)
        h = int(avail.height() * 0.85)
        x = avail.x() + (avail.width() - w) // 2 + 30
        y = avail.y() + (avail.height() - h) // 2 + 30
        win.setGeometry(x, y, w, h)
    win.show()
    _extra_windows.append(win)
    # 視窗關閉時從列表移除
    win.destroyed.connect(lambda: _extra_windows.remove(win) if win in _extra_windows else None)


# ==========================
# 檔案關聯
# ==========================
def _register_assoc(ui: ImervueMainWindow):
    from Imervue.system.file_association import register_file_association
    lang = language_wrapper.language_word_dict
    ok, msg = register_file_association()
    if ok:
        if hasattr(ui, "toast"):
            ui.toast.info(lang.get("file_assoc_done", "File association registered!"))
    else:
        if msg == "need_admin":
            if hasattr(ui, "toast"):
                ui.toast.info(lang.get("file_assoc_need_admin", "Administrator privileges required"))
        else:
            if hasattr(ui, "toast"):
                ui.toast.info(f"Error: {msg}")


def _paste_from_clipboard(ui: ImervueMainWindow) -> None:
    """Open the annotation dialog on the current clipboard image, if any."""
    from Imervue.gui.annotation_dialog import open_annotation_for_clipboard_image
    lang = language_wrapper.language_word_dict
    monitor = getattr(ui, "clipboard_monitor", None)
    img = monitor.grab_current_image() if monitor is not None else None
    if img is None:
        if hasattr(ui, "toast"):
            ui.toast.info(
                lang.get(
                    "file_menu_paste_clipboard_empty",
                    "Clipboard does not contain an image",
                )
            )
        return
    open_annotation_for_clipboard_image(ui, img)


def _toggle_clipboard_monitor(ui: ImervueMainWindow, enabled: bool) -> None:
    monitor = getattr(ui, "clipboard_monitor", None)
    if monitor is None:
        return
    monitor.set_enabled(enabled)
    lang = language_wrapper.language_word_dict
    if hasattr(ui, "toast"):
        msg_key = (
            "file_menu_clipboard_monitor_on" if enabled
            else "file_menu_clipboard_monitor_off"
        )
        default = "Clipboard auto-annotate ON" if enabled else "Clipboard auto-annotate OFF"
        ui.toast.info(lang.get(msg_key, default))


def _open_bookmarks(ui: ImervueMainWindow):
    from Imervue.gui.bookmark_dialog import open_bookmark_dialog
    open_bookmark_dialog(ui.viewer)


def _open_tag_album(ui: ImervueMainWindow):
    from Imervue.gui.tag_album_dialog import open_tag_album_dialog
    open_tag_album_dialog(ui.viewer)


def _unregister_assoc(ui: ImervueMainWindow):
    from Imervue.system.file_association import unregister_file_association
    lang = language_wrapper.language_word_dict
    ok, msg = unregister_file_association()
    if ok:
        if hasattr(ui, "toast"):
            ui.toast.info(lang.get("file_assoc_removed", "File association removed!"))
    else:
        if msg == "need_admin":
            if hasattr(ui, "toast"):
                ui.toast.info(lang.get("file_assoc_need_admin", "Administrator privileges required"))
        else:
            if hasattr(ui, "toast"):
                ui.toast.info(f"Error: {msg}")

