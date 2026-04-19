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
        reg_action = assoc_menu.addAction(
            lang.get("file_assoc_register", "Register 'Open with Imervue'")
        )
        reg_action.triggered.connect(lambda: _register_assoc(ui_we_want_to_set))
        unreg_action = assoc_menu.addAction(
            lang.get("file_assoc_unregister", "Remove file association")
        )
        unreg_action.triggered.connect(lambda: _unregister_assoc(ui_we_want_to_set))

    file_menu.addSeparator()

    # Session / Workspace
    session_menu = file_menu.addMenu(lang.get("session_menu", "Session"))
    save_session_action = session_menu.addAction(
        lang.get("session_save", "Save Session\u2026"))
    save_session_action.triggered.connect(
        lambda: _save_session(ui_we_want_to_set))
    load_session_action = session_menu.addAction(
        lang.get("session_load", "Load Session\u2026"))
    load_session_action.triggered.connect(
        lambda: _load_session(ui_we_want_to_set))

    # 外部編輯器
    editors_action = file_menu.addAction(
        lang.get("ext_editor_menu", "External Editors\u2026"))
    editors_action.triggered.connect(
        lambda: _open_external_editors_settings(ui_we_want_to_set))

    # Launch current image in a configured external editor
    open_in_menu = file_menu.addMenu(
        lang.get("ext_editor_open_in", "Open in External Editor"))
    _populate_open_in_editor_menu(ui_we_want_to_set, open_in_menu)

    file_menu.addSeparator()

    # 自訂快捷鍵
    shortcut_action = file_menu.addAction(
        lang.get("shortcut_title", "Keyboard Shortcuts"))
    shortcut_action.triggered.connect(lambda: _open_shortcut_settings(ui_we_want_to_set))

    file_menu.addSeparator()

    exit_action = file_menu.addAction(lang.get("main_window_exit"))
    exit_action.triggered.connect(ui_we_want_to_set.close)

    # ===== Tile Size 選單 =====
    view_menu = ui_we_want_to_set.menuBar().addMenu(
        language_wrapper.language_word_dict.get("main_window_tile_size")
    )

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

    # ===== Grid / List 檢視切換 =====
    view_menu.addSeparator()
    mode_menu = view_menu.addMenu(lang.get("view_browse_mode", "Browse Mode"))
    mode_group = QActionGroup(ui_we_want_to_set)
    mode_group.setExclusive(True)

    action_grid = mode_menu.addAction(lang.get("view_mode_grid", "Grid"))
    action_grid.setCheckable(True)
    action_grid.setChecked(True)
    mode_group.addAction(action_grid)
    action_grid.triggered.connect(
        lambda: ui_we_want_to_set.set_browse_mode("grid")
    )

    action_list = mode_menu.addAction(lang.get("view_mode_list", "List"))
    action_list.setCheckable(True)
    mode_group.addAction(action_list)
    action_list.triggered.connect(
        lambda: ui_we_want_to_set.set_browse_mode("list")
    )
    ui_we_want_to_set._mode_action_grid = action_grid
    ui_we_want_to_set._mode_action_list = action_list

    # ===== 縮圖排列密度 =====
    view_menu.addSeparator()
    density_menu = view_menu.addMenu(
        lang.get("view_tile_density", "Thumbnail Density")
    )
    density_group = QActionGroup(ui_we_want_to_set)
    density_group.setExclusive(True)
    density_presets = [
        (0, "view_density_compact", "Compact"),
        (8, "view_density_standard", "Standard"),
        (16, "view_density_relaxed", "Relaxed"),
    ]
    current_padding = ui_we_want_to_set.viewer.tile_padding
    for pad, key, fallback in density_presets:
        a = density_menu.addAction(lang.get(key, fallback))
        a.setCheckable(True)
        if pad == current_padding:
            a.setChecked(True)
        density_group.addAction(a)
        a.triggered.connect(
            lambda checked, p=pad: ui_we_want_to_set.change_tile_padding(p)
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
        if hasattr(ui_we_want_to_set, "breadcrumb"):
            ui_we_want_to_set.breadcrumb.set_path(folder)

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
        "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp *.gif *.apng *.svg "
        "*.cr2 *.nef *.arw *.dng *.raf *.orf)"
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
    from Imervue.Imervue_main_window import ImervueMainWindow as _MainWindow
    win = _MainWindow()
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
    elif msg == "need_admin":
        if hasattr(ui, "toast"):
            ui.toast.info(lang.get("file_assoc_need_admin", "Administrator privileges required"))
    elif hasattr(ui, "toast"):
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
    elif msg == "need_admin":
        if hasattr(ui, "toast"):
            ui.toast.info(lang.get("file_assoc_need_admin", "Administrator privileges required"))
    elif hasattr(ui, "toast"):
        ui.toast.info(f"Error: {msg}")


def _open_shortcut_settings(ui: ImervueMainWindow):
    from Imervue.gui.shortcut_settings_dialog import open_shortcut_settings
    open_shortcut_settings(ui)


def _save_session(ui: ImervueMainWindow) -> None:
    from Imervue.sessions.session_manager import save_session_to_path, SESSION_EXT
    lang = language_wrapper.language_word_dict
    start = user_setting_dict.get("user_last_folder") or ""
    file_path, _ = QFileDialog.getSaveFileName(
        ui,
        lang.get("session_save", "Save Session"),
        start,
        f"Imervue session (*{SESSION_EXT})",
    )
    if not file_path:
        return
    out = save_session_to_path(ui, file_path)
    if hasattr(ui, "toast"):
        ui.toast.info(
            lang.get("session_saved", "Session saved to {path}").format(path=out)
        )


def _load_session(ui: ImervueMainWindow) -> None:
    from Imervue.sessions.session_manager import (
        load_session_from_path, restore_session, SESSION_EXT,
    )
    lang = language_wrapper.language_word_dict
    start = user_setting_dict.get("user_last_folder") or ""
    file_path, _ = QFileDialog.getOpenFileName(
        ui,
        lang.get("session_load", "Load Session"),
        start,
        f"Imervue session (*{SESSION_EXT})",
    )
    if not file_path:
        return
    try:
        data = load_session_from_path(file_path)
    except (OSError, ValueError) as exc:
        if hasattr(ui, "toast"):
            ui.toast.info(f"Session load failed: {exc}")
        return
    counts = restore_session(ui, data)
    if hasattr(ui, "toast"):
        ui.toast.info(
            lang.get(
                "session_restored",
                "Restored {ok} items (skipped {skip})",
            ).format(ok=counts["applied"], skip=counts["skipped"])
        )


def _open_external_editors_settings(ui: ImervueMainWindow) -> None:
    from Imervue.gui.external_editors_settings import open_external_editors_settings
    open_external_editors_settings(ui)


def _populate_open_in_editor_menu(ui: ImervueMainWindow, menu) -> None:
    """Fill ``menu`` with one entry per configured external editor."""
    from Imervue.external.editors import load_editors
    lang = language_wrapper.language_word_dict
    menu.clear()
    editors = load_editors()
    if not editors:
        placeholder = menu.addAction(
            lang.get("ext_editor_none_configured", "(None configured)"))
        placeholder.setEnabled(False)
        return
    for entry in editors:
        action = menu.addAction(entry.name)
        action.triggered.connect(
            lambda checked=False, e=entry: _launch_editor_on_current(ui, e))


def _launch_editor_on_current(ui: ImervueMainWindow, entry) -> None:
    from Imervue.external.editors import launch_editor
    viewer = ui.viewer
    images = getattr(viewer.model, "images", [])
    idx = getattr(viewer, "current_index", -1)
    if not (0 <= idx < len(images)):
        return
    path = images[idx]
    ok = launch_editor(entry, path)
    if hasattr(ui, "toast"):
        lang = language_wrapper.language_word_dict
        msg_key = "ext_editor_launched" if ok else "ext_editor_launch_failed"
        fallback = "Launched {name}" if ok else "Failed to launch {name}"
        ui.toast.info(lang.get(msg_key, fallback).format(name=entry.name))

