import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, QFileSystemWatcher
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QFileSystemModel, QSplitter, QSizePolicy,
    QStatusBar, QProgressBar, QMenu, QTabBar, QTabWidget,
    QStackedWidget,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from Imervue.system.app_paths import icon_path as _app_icon_path
from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.gui.exif_sidebar import ExifSidebar
from Imervue.gui.toast import ToastManager
from Imervue.integration_guide import _init_plugin_system_example
from Imervue.menu.extra_tools_menu import build_extra_tools_menu
from Imervue.menu.file_menu import build_file_menu
from Imervue.menu.filter_menu import build_filter_menu
from Imervue.menu.language_menu import build_language_menu
from Imervue.menu.modify_menu import build_modify_menu
from Imervue.menu.recent_menu import rebuild_recent_menu
from Imervue.menu.sort_menu import build_sort_menu
from Imervue.menu.tip_menu import build_tip_menu
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import (
    write_user_setting, read_user_setting, user_setting_dict, cancel_pending_save,
)
import contextlib


class _FileTreeView(QTreeView):
    """QTreeView with Delete key and right-click context menu."""

    def __init__(self, main_window: "ImervueMainWindow"):
        super().__init__()
        self._main_window = main_window
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ---------- Keyboard shortcuts ----------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Delete:
            self._delete_selected()
            return
        if key == Qt.Key.Key_F5:
            self._refresh_tree()
            return
        super().keyPressEvent(event)

    def _refresh_tree(self) -> None:
        """Force QFileSystemModel to re-scan the current root.

        Useful when external tools have changed the folder contents and
        Qt's native watcher hasn't picked it up yet.
        """
        model: QFileSystemModel = self.model()
        root = self.rootIndex()
        if not root.isValid():
            return
        path = model.filePath(root)
        if path:
            # setRootPath() re-stats the directory even if the value is the same
            model.setRootPath("")
            model.setRootPath(path)
            self.setRootIndex(model.index(path))

    def _delete_selected(self):
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        model: QFileSystemModel = self.model()
        path = model.filePath(indexes[0])
        if not path or not Path(path).exists():
            return
        self._delete_path(path)

    # ---------- Right-click menu ----------

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
        model: QFileSystemModel = self.model()
        path = model.filePath(index)
        if not path:
            return

        lang = language_wrapper.language_word_dict
        menu = QMenu(self)

        # Show in Explorer
        action_explorer = menu.addAction(
            lang.get("tree_open_in_explorer", "Open in Explorer")
        )
        action_explorer.triggered.connect(lambda: self._open_in_explorer(path))

        # Open containing folder
        if Path(path).is_file():
            action_folder = menu.addAction(
                lang.get("tree_open_folder", "Open Containing Folder")
            )
            action_folder.triggered.connect(
                lambda: self._open_in_explorer(str(Path(path).parent), select=False)
            )

        menu.addSeparator()

        # Copy path
        action_copy = menu.addAction(lang.get("right_click_copy_path", "Copy Path"))
        action_copy.triggered.connect(
            lambda: QApplication.clipboard().setText(path)
        )

        menu.addSeparator()

        # New Folder (inside the clicked folder, or the clicked file's parent)
        action_new = menu.addAction(lang.get("tree_new_folder", "New Folder"))
        target_dir = path if Path(path).is_dir() else str(Path(path).parent)
        action_new.triggered.connect(lambda: self._create_new_folder(target_dir))

        # Refresh
        action_refresh = menu.addAction(lang.get("tree_refresh", "Refresh"))
        action_refresh.triggered.connect(self._refresh_tree)

        # Expand / collapse all children
        if Path(path).is_dir():
            action_expand = menu.addAction(lang.get("tree_expand_all", "Expand All"))
            action_expand.triggered.connect(lambda: self.expandRecursively(index))
            action_collapse = menu.addAction(lang.get("tree_collapse_all", "Collapse All"))
            action_collapse.triggered.connect(lambda: self.collapse(index))

        menu.addSeparator()

        # Delete
        action_del = menu.addAction(lang.get("tree_delete", "Delete"))
        action_del.triggered.connect(lambda: self._delete_path(path))

        menu.exec(self.viewport().mapToGlobal(pos))

    def _create_new_folder(self, parent_dir: str) -> None:
        """Prompt for a folder name and create it under ``parent_dir``."""
        from PySide6.QtWidgets import QInputDialog
        lang = language_wrapper.language_word_dict
        name, ok = QInputDialog.getText(
            self,
            lang.get("tree_new_folder", "New Folder"),
            lang.get("tree_new_folder_prompt", "Folder name:"),
        )
        if not ok or not name.strip():
            return
        try:
            target = Path(parent_dir) / name.strip()
            target.mkdir(parents=False, exist_ok=False)
            self._refresh_tree()
        except FileExistsError:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.warning(
                    lang.get("tree_folder_exists", "Folder already exists")
                )
        except OSError as exc:
            if hasattr(self._main_window, "toast"):
                self._main_window.toast.error(
                    f"{lang.get('tree_new_folder_failed', 'Create failed')}: {exc}"
                )

    @staticmethod
    def _open_in_explorer(path: str, select: bool = True):
        with contextlib.suppress(Exception):
            if sys.platform == "win32":
                if select and Path(path).is_file():
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                else:
                    subprocess.Popen(["explorer", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R" if select else "", path])
            else:
                target = path if Path(path).is_dir() else str(Path(path).parent)
                subprocess.Popen(["xdg-open", target])

    def _delete_path(self, path: str):
        if not Path(path).exists():
            return
        viewer = self._main_window.viewer
        images = viewer.model.images
        if Path(path).is_file() and path in images:
            self._delete_from_viewer_list(path, viewer, images)
        else:
            self._delete_external(path)

    def _delete_from_viewer_list(self, path: str, viewer, images: list[str]) -> None:
        idx = images.index(path)
        images.pop(idx)
        viewer.undo_stack.append({
            "mode": "delete",
            "deleted_paths": [path],
            "indices": [idx],
            "restored": False,
        })
        tex = viewer.tile_textures.pop(path, None)
        if tex is not None:
            from OpenGL.GL import glDeleteTextures
            glDeleteTextures([tex])
        viewer.tile_cache.pop(path, None)
        self._refresh_viewer_after_delete(viewer, images, idx)
        self._notify_deleted(path)

    @staticmethod
    def _refresh_viewer_after_delete(viewer, images: list[str], idx: int) -> None:
        if viewer.tile_grid_mode:
            viewer.tile_rects.clear()
            viewer.update()
            return
        if not viewer.deep_zoom:
            return
        if images:
            viewer.current_index = min(idx, len(images) - 1)
            viewer.load_deep_zoom_image(images[viewer.current_index])
        else:
            viewer.deep_zoom = None
            viewer.current_index = 0
            viewer.tile_grid_mode = True
            viewer.update()

    def _delete_external(self, path: str) -> None:
        from Imervue.gpu_image_view.actions.keyboard_actions import _send_to_trash
        if _send_to_trash(path):
            self._notify_deleted(path)

    def _notify_deleted(self, path: str) -> None:
        if not hasattr(self._main_window, "toast"):
            return
        lang = language_wrapper.language_word_dict
        self._main_window.toast.info(
            lang.get("tree_deleted", "Moved to trash: {name}").format(
                name=Path(path).name
            )
        )


class ImervueMainWindow(QMainWindow):
    def __init__(self, debug: bool = False):
        super().__init__()

        self.setWindowTitle("Imervue")

        # Windows 平台設定 AppUserModelID
        # Set AppUserModelID for Windows platform
        self.id = "Imervue"
        try:
            from ctypes import windll
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.id)
        except (ImportError, AttributeError):
            pass

        read_user_setting()
        last_folder = user_setting_dict.get("user_last_folder", "")

        if last_folder and Path(last_folder).is_dir():
            QTimer.singleShot(
                0,
                lambda: self._open_startup_folder(last_folder)
            )

        # 語言支援
        # Language support
        self.language_wrapper = language_wrapper
        self.language_wrapper.reset_language(user_setting_dict.get("language", "English"))

        self.icon_path = _app_icon_path()
        self.icon = QIcon(str(self.icon_path))
        self.setWindowIcon(self.icon)

        # ===== 頂層 QTabWidget =====
        # Tab 0: Imervue 主頁面（不可關閉）
        # Tab 1: 修改面板（左面板 | 圖片 | 右面板）
        self._main_tabs = QTabWidget()
        self._main_tabs.setTabsClosable(False)
        self._main_tabs.setMovable(False)
        self.setCentralWidget(self._main_tabs)

        # --------------------------------------------------------
        # Tab 0: Imervue 主頁面
        # --------------------------------------------------------
        imervue_page = QWidget()
        imervue_layout = QVBoxLayout(imervue_page)
        imervue_layout.setContentsMargins(0, 0, 0, 0)
        imervue_layout.setSpacing(0)

        splitter = QSplitter()
        imervue_layout.addWidget(splitter)

        # ===== 左側檔案樹 =====
        self.model = QFileSystemModel()
        # 只篩選圖片格式 + 資料夾，隱藏不符合的檔案
        self.model.setNameFilters([
            "*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff", "*.tif", "*.webp",
            "*.gif", "*.apng", "*.svg",
            "*.cr2", "*.nef", "*.arw", "*.dng", "*.raf", "*.orf",
        ])
        self.model.setNameFilterDisables(False)

        # 設定起始路徑：有上次資料夾就用，否則從根開始
        start_path = last_folder if last_folder and Path(last_folder).is_dir() else ""
        self.model.setRootPath(start_path)

        self.tree = _FileTreeView(self)
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(start_path))
        # 只顯示「名稱」欄，隱藏大小/類型/日期（省掉大量 stat() 呼叫）
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.header().setStretchLastSection(True)
        self.tree.setColumnWidth(0, 400)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(False)
        self.tree.clicked.connect(self.on_file_clicked)

        # 目錄載入完成後確保樹狀圖更新
        self.model.directoryLoaded.connect(self._on_directory_loaded)

        # ===== 右側 GPU Viewer + Label =====
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_widget.setLayout(right_layout)

        # ===== 圖片分頁 (Browser-style tab bar) =====
        # 每個分頁 = 一張目前開啟的 deep-zoom 圖片。分頁列常駐顯示，
        # 切換分頁會觸發 ``load_deep_zoom_image`` 到對應路徑。
        # Tile grid / 資料夾瀏覽時分頁狀態保持不動，僅在 deep zoom 時同步。
        self._image_tabs: list[dict] = []  # [{"path": str, "title": str}, ...]
        self._tab_switching: bool = False  # re-entrancy guard

        self._tab_bar = QTabBar()
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideMiddle)
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)
        right_layout.addWidget(self._tab_bar)

        # ===== 麵包屑路徑列 =====
        from Imervue.gui.breadcrumb_bar import BreadcrumbBar
        self.breadcrumb = BreadcrumbBar(self)
        right_layout.addWidget(self.breadcrumb)

        self.filename_label = QLabel(
            language_wrapper.language_word_dict.get("main_window_current_filename")
        )
        self.filename_label.setMinimumHeight(16)  # 保證有高度
        self.filename_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.filename_label.setWordWrap(False)
        self.filename_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right_layout.addWidget(self.filename_label, stretch=0)

        from Imervue.gpu_image_view.gpu_image_view import GPUImageView
        from Imervue.gui.develop_panel import DevelopPanel
        self.viewer = GPUImageView(main_window=self)

        self.exif_sidebar = ExifSidebar(self)

        # ===== 檢視模式堆疊 (Grid/List/Dual) =====
        # viewer 在 index 0，ImageListView 在 index 1，DualImageView 在 index 2。
        from Imervue.gui.image_list_view import ImageListView
        from Imervue.gui.dual_image_view import DualImageView
        self.image_list_view = ImageListView(self)
        self.image_list_view.image_activated.connect(self._on_list_activated)

        self.dual_view = DualImageView(self)
        self.dual_view.closed.connect(self._on_dual_closed)

        self._view_stack = QStackedWidget()
        self._view_stack.addWidget(self.viewer)          # 0: viewer
        self._view_stack.addWidget(self.image_list_view)   # 1: list
        self._view_stack.addWidget(self.dual_view)         # 2: dual
        self._browse_mode: str = "grid"  # "grid" | "list"
        self._dual_active: bool = False
        self._pre_dual_mode: str = "grid"

        viewer_row = QSplitter(Qt.Orientation.Horizontal)
        viewer_row.addWidget(self._view_stack)
        viewer_row.addWidget(self.exif_sidebar)
        viewer_row.setStretchFactor(0, 1)
        viewer_row.setStretchFactor(1, 0)
        right_layout.addWidget(viewer_row, stretch=1)

        def _on_name_changed(name):
            self.filename_label.setText(
                language_wrapper.language_word_dict.get("main_window_current_filename_format").format(name=name))
            self.exif_sidebar.update_info()
            # Keep the tab bar in lockstep with whatever image the viewer
            # now shows. Only sync in deep-zoom mode — tile grid / folder
            # browsing intentionally doesn't create tabs.
            with contextlib.suppress(Exception):
                images = self.viewer.model.images
                idx = self.viewer.current_index
                if self.viewer.deep_zoom and 0 <= idx < len(images):
                    self._sync_current_tab_with_path(images[idx])

        self.viewer.on_filename_changed = _on_name_changed

        splitter.addWidget(self.tree)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 1000])

        self._main_tabs.addTab(imervue_page, "Imervue")

        # --------------------------------------------------------
        # Tab 1: 修改面板 — 左面板 | 圖片 | 右面板
        # --------------------------------------------------------
        lang = language_wrapper.language_word_dict
        self.modify_panel = DevelopPanel(self.viewer)
        self.modify_panel.recipe_committed.connect(
            self.viewer._on_recipe_committed,
        )

        modify_page = QWidget()
        modify_layout = QHBoxLayout(modify_page)
        modify_layout.setContentsMargins(0, 0, 0, 0)
        modify_layout.setSpacing(0)

        modify_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左面板：註解 + 方向
        self.modify_panel.build_left_panel(modify_splitter)
        # 右面板：顯影滑桿 + 重設（中間的 viewer 會在切換分頁時 reparent 進來）
        self.modify_panel.build_right_panel(modify_splitter)

        modify_splitter.setStretchFactor(0, 0)
        modify_splitter.setStretchFactor(1, 0)

        modify_layout.addWidget(modify_splitter)
        self._modify_splitter = modify_splitter

        self._main_tabs.addTab(
            modify_page,
            lang.get("modify_menu_title", "Modify"),
        )

        # 切換分頁時把 viewer 移到正確的位置
        self._imervue_viewer_row = viewer_row
        self._main_tabs.currentChanged.connect(self._on_main_tab_changed)

        # ===== 狀態列 =====
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("")
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(180)
        self._progress_bar.setVisible(False)
        # Permanent-side info slots: index · resolution · size · zoom · cursor
        # These are only populated by the viewer; empty strings keep the
        # separators from showing up when nothing is loaded yet.
        self._status_info_index = QLabel("")
        self._status_info_resolution = QLabel("")
        self._status_info_size = QLabel("")
        self._status_info_zoom = QLabel("")
        self._status_info_cursor = QLabel("")
        self._status_info_label = QLabel("")  # Colour-label chip
        for lbl in (
                self._status_info_index, self._status_info_resolution,
                self._status_info_size, self._status_info_zoom,
                self._status_info_cursor,
        ):
            lbl.setStyleSheet("color: #aaa; padding: 0 6px;")
        self._status_info_label.setStyleSheet(
            "padding: 0 8px; border-radius: 3px;"
        )
        self._status_bar.addWidget(self._status_label, stretch=1)
        self._status_bar.addPermanentWidget(self._status_info_label)
        self._status_bar.addPermanentWidget(self._status_info_index)
        self._status_bar.addPermanentWidget(self._status_info_resolution)
        self._status_bar.addPermanentWidget(self._status_info_size)
        self._status_bar.addPermanentWidget(self._status_info_zoom)
        self._status_bar.addPermanentWidget(self._status_info_cursor)
        self._status_bar.addPermanentWidget(self._progress_bar)

        # ===== Toast 通知 =====
        self.toast = ToastManager(self.viewer)

        # ===== 剪貼簿監聽（ShareX 風格 PrintScreen → 註解視窗） =====
        from Imervue.system.clipboard_monitor import ClipboardMonitor
        self.clipboard_monitor = ClipboardMonitor(self)
        self.clipboard_monitor.image_captured.connect(self._on_clipboard_image_captured)

        # ===== 選單列 =====
        self.create_menu()

        _init_plugin_system_example(self)

        # ===== 分頁快捷鍵 =====
        # Ctrl+T 新分頁 / Ctrl+W 關閉 / Ctrl+Tab 下一個 / Ctrl+Shift+Tab 上一個。
        # 模仿瀏覽器行為，註冊在 main window 範圍內。
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._new_tab)
        QShortcut(QKeySequence("Ctrl+W"), self, activated=self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+Tab"), self, activated=self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, activated=self._prev_tab)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.toggle_browse_mode)

        # ===== 資料夾監控 =====
        self._folder_watcher = QFileSystemWatcher(self)
        self._folder_watcher.directoryChanged.connect(self._on_watched_folder_changed)
        self._folder_refresh_timer = QTimer(self)
        self._folder_refresh_timer.setSingleShot(True)
        self._folder_refresh_timer.setInterval(500)  # 去抖動 500ms
        self._folder_refresh_timer.timeout.connect(self._do_folder_refresh)

        # ===== 檔案樹遞迴監控（watchdog）=====
        # QFileSystemModel 內建的 watcher 對外部批次變更（git checkout、rsync、
        # 拖放）反應不及時。watchdog 用獨立執行緒遞迴監看樹根，事件透過 Qt
        # signal 跨執行緒回到 UI 並去抖動觸發 model 重新整理。
        from Imervue.system.file_tree_watcher import FileTreeWatchdog
        self._tree_watchdog = FileTreeWatchdog(self)
        self._tree_watchdog.bind_model(self.model)

        # ===== 還原視窗位置與大小（多螢幕適配） =====
        self._restore_window_geometry()

        # ===== Debug =====
        # Debug 模式下自動關閉
        # Auto close in debug mode
        if debug:
            self.debug_timer = QTimer()
            self.debug_timer.setInterval(10000)
            self.debug_timer.timeout.connect(self.debug_close)
            self.debug_timer.start()

    # ==========================
    # 主分頁切換（Imervue ↔ 修改）
    # ==========================
    def _on_main_tab_changed(self, idx: int) -> None:
        """Switch between Imervue (viewer) and Modify (annotation canvas) tabs."""
        if idx == 1:
            # 切到修改分頁 → 綁定圖片，canvas 會自動插入 splitter 中間
            images = self.viewer.model.images
            path = None
            if images and 0 <= self.viewer.current_index < len(images):
                path = images[self.viewer.current_index]
            self.modify_panel.bind_to_path(path)
        else:
            # 切回 Imervue 主頁
            self.exif_sidebar.update_info()

    # ==========================
    # 選單
    # ==========================
    def create_menu(self):
        build_file_menu(self)
        build_extra_tools_menu(self)
        build_sort_menu(self)
        build_filter_menu(self)
        build_language_menu(self)
        # Plugin menu is built after plugin system init (in integration_guide.py)
        build_tip_menu(self)
        # 「修改」選單 — 建立時隱藏，deep zoom 進入時由 viewer 顯示。
        build_modify_menu(self)

    # ==========================
    # 狀態列
    # ==========================
    def set_status(self, text: str):
        self._status_label.setText(text)

    def show_progress(self, current: int, total: int):
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "status_loading_progress", "Loading {current}/{total}..."
            ).format(current=current, total=total)
        )
        if current >= total:
            QTimer.singleShot(800, self._hide_progress)

    def _hide_progress(self):
        self._progress_bar.setVisible(False)
        self._status_label.setText(
            language_wrapper.language_word_dict.get("status_ready", "Ready")
        )

    # ---------- Status bar info slots ----------
    def update_status_info(
            self,
            *,
            index: str | None = None,
            resolution: str | None = None,
            size: str | None = None,
            zoom: str | None = None,
            cursor: str | None = None,
            label: str | None = None,
    ) -> None:
        """Update any subset of the permanent info slots in the status bar.

        Called by the viewer whenever the shown image, zoom level, or mouse
        position changes. Passing ``None`` leaves a slot untouched; passing
        an empty string clears it.
        """
        if index is not None:
            self._status_info_index.setText(index)
        if resolution is not None:
            self._status_info_resolution.setText(resolution)
        if size is not None:
            self._status_info_size.setText(size)
        if zoom is not None:
            self._status_info_zoom.setText(zoom)
        if cursor is not None:
            self._status_info_cursor.setText(cursor)
        if label is not None:
            self._apply_status_label(label)

    def _apply_status_label(self, color: str) -> None:
        """Render the colour-label chip as a coloured pill, or hide when empty."""
        from Imervue.user_settings.color_labels import COLOR_RGB
        if not color:
            self._status_info_label.setText("")
            self._status_info_label.setStyleSheet(
                "padding: 0 8px; border-radius: 3px;"
            )
            return
        rgb = COLOR_RGB.get(color)
        if rgb is None:
            self._status_info_label.setText("")
            return
        r, g, b = rgb
        display = language_wrapper.language_word_dict.get(
            f"color_label_{color}", color.title()
        )
        self._status_info_label.setText(display)
        self._status_info_label.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: white;"
            " padding: 0 8px; border-radius: 3px; font-weight: bold;"
        )

    def clear_status_info(self) -> None:
        """Wipe all permanent info slots — used when leaving an image."""
        self.update_status_info(
            index="", resolution="", size="", zoom="", cursor="", label="",
        )

    # ==========================
    # 檢視模式 (Grid / List)
    # ==========================
    def is_list_mode(self) -> bool:
        return self._browse_mode == "list"

    def set_browse_mode(self, mode: str) -> None:
        """Switch between tile grid (mode='grid') and the QTableView list."""
        if mode not in ("grid", "list"):
            return
        if mode == self._browse_mode:
            return
        self._browse_mode = mode
        if mode == "list":
            # Sync list view with whatever the viewer currently knows about
            self.refresh_list_view()
            self._view_stack.setCurrentIndex(1)
        else:
            self._view_stack.setCurrentIndex(0)
            # If viewer was sitting on tile grid, re-render it fresh
            if self.viewer.model.images and not self.viewer.deep_zoom:
                self.viewer.tile_grid_mode = True
                self.viewer.update()

        # Sync View menu radio buttons with the current mode
        grid_action = getattr(self, "_mode_action_grid", None)
        list_action = getattr(self, "_mode_action_list", None)
        if grid_action is not None:
            grid_action.setChecked(mode == "grid")
        if list_action is not None:
            list_action.setChecked(mode == "list")

    def toggle_browse_mode(self) -> None:
        self.set_browse_mode("list" if self._browse_mode == "grid" else "grid")

    def refresh_list_view(self) -> None:
        """Populate the list view from the viewer's current image list."""
        self.image_list_view.set_paths(list(self.viewer.model.images))

    def _on_list_activated(self, path: str) -> None:
        """Double-clicking a row opens that image in the deep-zoom viewer.

        We swap the stack back to the viewer so deep zoom is visible; Esc
        from deep zoom takes the user back to the list because
        ``_browse_mode`` is still ``"list"``.
        """
        if not path:
            return
        images = self.viewer.model.images
        if path in images:
            self.viewer.current_index = images.index(path)
        self._view_stack.setCurrentIndex(0)
        self.viewer.tile_grid_mode = False
        self.viewer.load_deep_zoom_image(path)

    def after_deep_zoom_escape(self) -> None:
        """Called by the viewer after Esc leaves deep zoom.

        If the user was browsing in list mode, restore the list view instead
        of the tile grid.
        """
        if self._browse_mode == "list":
            self._view_stack.setCurrentIndex(1)

    # ==========================
    # 雙圖顯示 (Split / Manga)
    # ==========================
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

    # ==========================
    # 多螢幕視窗
    # ==========================
    def _ensure_multi_monitor(self):
        ctrl = getattr(self, "_multi_monitor", None)
        if ctrl is None:
            from Imervue.gui.multi_monitor_window import MultiMonitorController
            ctrl = MultiMonitorController(self)
            self._multi_monitor = ctrl
        return ctrl

    def toggle_multi_monitor_window(self) -> None:
        self._ensure_multi_monitor().toggle()

    # ==========================
    # 劇場模式 (Theater mode)
    # ==========================
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
            self.tree,
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

    def change_tile_size(self, size):
        if size != "None":
            self.viewer.thumbnail_size = size
        else:
            self.viewer.thumbnail_size = None

        # 如果目前有載入圖片，重新刷新
        if self.viewer.model.images:
            if len(self.viewer.model.images) > 1:
                self.viewer.clear_tile_grid()
                self.viewer.load_tile_grid_async(image_paths=self.viewer.model.images)
            else:
                self.viewer.tile_grid_mode = False
                self.viewer.load_deep_zoom_image(self.viewer.model.images[0])

    def change_tile_padding(self, padding: int) -> None:
        """Set thumbnail-grid padding and persist — 0 compact, 8 standard, 16 relaxed."""
        padding = int(max(0, min(64, padding)))
        self.viewer.tile_padding = padding
        user_setting_dict["tile_padding"] = padding
        if self.viewer.tile_grid_mode:
            self.viewer.update()

    # ==========================
    # 資料夾監控
    # ==========================
    def watch_folder(self, folder: str):
        """監控指定資料夾，發生變更時自動刷新"""
        dirs = self._folder_watcher.directories()
        if dirs:
            self._folder_watcher.removePaths(dirs)
        if folder:
            self._folder_watcher.addPath(folder)
        # 同步啟動遞迴 watchdog 觀察整個樹根，QFileSystemModel 才會即時更新
        if folder and hasattr(self, "_tree_watchdog"):
            self._tree_watchdog.watch(folder)

    def _on_watched_folder_changed(self, _path: str):
        """資料夾內容變更 → 啟動去抖動計時器"""
        self._folder_refresh_timer.start()

    def _do_folder_refresh(self):
        """去抖動後重新掃描資料夾並更新 tile grid"""
        viewer = self.viewer
        if not viewer.model.images:
            return
        # 取得目前資料夾
        first = viewer.model.images[0]
        folder = str(Path(first).parent)
        if not Path(folder).is_dir():
            return

        from Imervue.gpu_image_view.images.image_loader import _scan_images
        new_images = _scan_images(folder)

        if set(new_images) != set(viewer.model.images):
            viewer.model.images = new_images
            if viewer.tile_grid_mode:
                viewer.clear_tile_grid()
                viewer.load_tile_grid_async(image_paths=new_images)
            viewer.update()

    # ==========================
    # 點擊檔案
    # ==========================
    def on_file_clicked(self, index):
        path = self.model.filePath(index)

        if Path(path).is_dir():
            # 點擊資料夾 → 導航進入並載入圖片
            self.model.setRootPath(path)
            self.tree.setRootIndex(self.model.index(path))
            self.viewer.clear_tile_grid()
            open_path(main_gui=self.viewer, path=path)
            self.filename_label.setText(
                language_wrapper.language_word_dict.get(
                    "main_window_current_folder_format"
                ).format(path=path)
            )
            self.breadcrumb.set_path(path)
            self.watch_folder(path)
        elif Path(path).is_file():
            self.viewer.clear_tile_grid()
            open_path(main_gui=self.viewer, path=path)
            self.breadcrumb.set_path(str(Path(path).parent))

        rebuild_recent_menu(self)

    def _on_directory_loaded(self, directory: str):
        """QFileSystemModel 目錄載入完成回調，確保樹狀圖正確顯示"""
        idx = self.model.index(directory)
        if idx.isValid():
            self.tree.update(idx)

    def _on_clipboard_image_captured(self, pil_image) -> None:
        """Open the annotation dialog when the clipboard monitor sees a new image."""
        from Imervue.gui.annotation_dialog import open_annotation_for_clipboard_image
        try:
            open_annotation_for_clipboard_image(self, pil_image)
        except Exception:
            import logging
            logging.getLogger("Imervue").exception("clipboard annotation dialog failed")

    def _open_startup_folder(self, folder: str):
        self.model.setRootPath(folder)
        self.tree.setRootIndex(self.model.index(folder))
        open_path(main_gui=self.viewer, path=folder)
        self.filename_label.setText(
            language_wrapper.language_word_dict.get(
                "main_window_current_folder_format"
            ).format(path=folder)
        )
        if hasattr(self, "breadcrumb"):
            self.breadcrumb.set_path(folder)
        self.watch_folder(folder)

    # ==========================
    # 圖片分頁 (Image tabs)
    # ==========================

    def _sync_current_tab_with_path(self, path: str) -> None:
        """Called whenever the viewer's deep-zoom image changes.

        Updates the currently-active tab's path/title, or creates the
        first tab if none exists yet. Guarded against re-entering while
        a tab switch is already loading a new image.
        """
        if self._tab_switching or not path:
            return
        title = Path(path).name

        idx = self._tab_bar.currentIndex()
        if idx < 0 or idx >= len(self._image_tabs):
            # No tab yet — create the first one automatically so the
            # user sees the image they just opened pinned in the bar.
            self._image_tabs.append({"path": path, "title": title})
            self._tab_switching = True
            try:
                new_idx = self._tab_bar.addTab(title)
                self._tab_bar.setTabToolTip(new_idx, path)
                self._tab_bar.setCurrentIndex(new_idx)
            finally:
                self._tab_switching = False
            return

        tab = self._image_tabs[idx]
        if tab["path"] == path:
            # Same image, nothing to update (avoids flicker on reloads).
            return
        tab["path"] = path
        tab["title"] = title
        self._tab_bar.setTabText(idx, title)
        self._tab_bar.setTabToolTip(idx, path)

    def _on_tab_changed(self, idx: int) -> None:
        """User clicked a tab — load its image into the viewer."""
        if self._tab_switching or idx < 0 or idx >= len(self._image_tabs):
            return
        path = self._image_tabs[idx]["path"]
        if not path or not Path(path).exists():
            return
        # Avoid reloading if the viewer is already on this image.
        if (self.viewer.deep_zoom
                and 0 <= self.viewer.current_index < len(self.viewer.model.images)
                and self.viewer.model.images[self.viewer.current_index] == path):
            return

        self._tab_switching = True
        try:
            self.viewer._clear_deep_zoom()
            open_path(main_gui=self.viewer, path=path)
        except Exception:
            import logging
            logging.getLogger("Imervue").exception(
                "tab switch to %s failed", path
            )
        finally:
            self._tab_switching = False

    def _on_tab_close(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._image_tabs):
            return
        self._image_tabs.pop(idx)
        self._tab_switching = True
        try:
            self._tab_bar.removeTab(idx)
        finally:
            self._tab_switching = False
        # Activate whichever tab is now current — Qt auto-picks a neighbor.
        new_idx = self._tab_bar.currentIndex()
        if new_idx >= 0 and new_idx < len(self._image_tabs):
            self._on_tab_changed(new_idx)

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        """Keep our tab state in sync when the user drags a tab to reorder."""
        if 0 <= from_idx < len(self._image_tabs) and 0 <= to_idx < len(self._image_tabs):
            moved = self._image_tabs.pop(from_idx)
            self._image_tabs.insert(to_idx, moved)

    def _new_tab(self) -> None:
        """Ctrl+T — open an empty placeholder tab.

        The placeholder has no path; the user fills it by clicking an
        image in the file tree, which triggers ``_sync_current_tab_with_path``
        via the viewer's filename-changed hook.
        """
        lang = language_wrapper.language_word_dict
        title = lang.get("tab_new", "New Tab")
        self._image_tabs.append({"path": "", "title": title})
        self._tab_switching = True
        try:
            new_idx = self._tab_bar.addTab(title)
            self._tab_bar.setCurrentIndex(new_idx)
        finally:
            self._tab_switching = False

    def _close_current_tab(self) -> None:
        idx = self._tab_bar.currentIndex()
        if idx >= 0:
            self._on_tab_close(idx)

    def _next_tab(self) -> None:
        count = self._tab_bar.count()
        if count <= 1:
            return
        self._tab_bar.setCurrentIndex(
            (self._tab_bar.currentIndex() + 1) % count
        )

    def _prev_tab(self) -> None:
        count = self._tab_bar.count()
        if count <= 1:
            return
        self._tab_bar.setCurrentIndex(
            (self._tab_bar.currentIndex() - 1) % count
        )

    # ==========================
    # 多螢幕視窗位置記憶
    # ==========================
    def _save_window_geometry(self) -> None:
        """Save window geometry + state into user_setting_dict."""
        import base64
        with contextlib.suppress(Exception):
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
        except Exception:
            self.showMaximized()
            return

        # 還原 state（工具列、dock 等）
        state_b64 = user_setting_dict.get("window_state", "")
        if state_b64:
            with contextlib.suppress(Exception):
                self.restoreState(QByteArray(base64.b64decode(state_b64)))

        # 檢查還原的位置是否在某個可用螢幕上; 若螢幕已拔除, 視窗可能落在不可見區域
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

    def closeEvent(self, event):
        import logging
        logging.getLogger("Imervue").info("closeEvent triggered")

        # --- 斷開分頁切換信號，避免銷毀過程中觸發 ---
        with contextlib.suppress(Exception):
            self._main_tabs.currentChanged.disconnect(self._on_main_tab_changed)

        # --- 停止 watchdog 觀察執行緒 ---
        with contextlib.suppress(Exception):
            if hasattr(self, "_tree_watchdog"):
                self._tree_watchdog.stop()

        # --- 安全關閉修改面板 ---
        # 停止預覽防抖計時器 — 未儲存的 recipe 變更在關閉時丟棄
        with contextlib.suppress(Exception):
            self.modify_panel._debounce.stop()
            self.modify_panel.recipe_committed.disconnect()
        with contextlib.suppress(Exception):
            self.modify_panel._destroy_canvas()
        with contextlib.suppress(Exception):
            self.modify_panel._undo_stack.clear()

        # --- 安全關閉 OpenGL viewer ---
        with contextlib.suppress(Exception):
            self.viewer.makeCurrent()
            self.viewer._delete_all_tile_textures()
            self.viewer._clear_deep_zoom()
            self.viewer.doneCurrent()

        # 儲存視窗位置與大小（在寫入設定之前）
        with contextlib.suppress(Exception):
            self._save_window_geometry()

        # 最優先：儲存使用者設定（在任何可能失敗的操作之前）
        # 先取消任何待處理的 debounced save，避免背景 timer 在關閉過程中
        # 與我們的 flush 競爭寫同一個檔案
        with contextlib.suppress(Exception):
            cancel_pending_save()
        with contextlib.suppress(Exception):
            write_user_setting()

        with contextlib.suppress(Exception):
            commit_pending_deletions(self.viewer)

        # Plugin hook: app closing
        if hasattr(self, "plugin_manager"):
            with contextlib.suppress(Exception):
                self.plugin_manager.dispatch_app_closing(self)
                self.plugin_manager.unload_all()

        event.accept()
        super().closeEvent(event)
        # 用 os._exit 直接結束行程，跳過 Python 解釋器關閉階段的 GC。
        # PySide6 在 Windows 上的已知問題：Python shutdown 時 GC 以
        # 不確定順序銷毀 QApplication 與 QWidget，shiboken 和 Qt 對物件
        # 所有權認知不一致 → double-free → heap corruption (0xC0000374)。
        # 所有重要資料（設定、刪除佇列、外掛）都已在上面儲存完畢，
        # 此處不再需要 Python 的正常清理流程。
        import os as _os
        _os._exit(0)

    @classmethod
    def debug_close(cls) -> None:
        """Debug 模式下強制退出 / Force exit in debug mode"""
        sys.exit(0)


if __name__ == "__main__":
    from Imervue.system.log_setup import setup_logging
    setup_logging()

    # HiDPI 支援
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = ImervueMainWindow()
    # 視窗位置由 _restore_window_geometry() 在 __init__ 中自動還原
    sys.exit(app.exec())
