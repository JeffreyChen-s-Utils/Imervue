import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, QFileSystemWatcher
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QSizePolicy,
    QStatusBar, QProgressBar, QMenu, QTabBar, QTabWidget,
    QComboBox, QDockWidget, QLineEdit, QPushButton, QStackedWidget,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from Imervue.system.app_paths import icon_path as _app_icon_path
from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.gui.exif_sidebar import ExifSidebar
from Imervue.gui.file_tree_view import _FileTreeView, _next_duplicate_name  # noqa: F401  # _next_duplicate_name re-exported for tests
from Imervue.gui.file_tree_sort import FileTreeSortProxy
from Imervue.gui.folder_thumbnail_model import DEFAULT_ICON_SIZE, FolderThumbnailModel
from Imervue.gui.toast import ToastManager
from Imervue.image.browser_state import (
    ImageFilterSpec,
    ImageMetadataIndex,
    _rating_matches,
    auto_match_same_name,
    detect_renamed_paths,
    filter_paths,
    migrate_view_path_state,
    missing_paths,
    relocate_root,
    remove_missing,
)
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

# 拖曳視窗時 moveEvent 連續觸發；停止移動這麼久後才檢查螢幕是否改變。
_SCREEN_ADAPT_DEBOUNCE_MS = 300

# Poll interval while waiting for the async folder scan to surface the image a
# startup deep-zoom restore is targeting (bounded by the retry count).
_DEEP_ZOOM_RESTORE_RETRY_MS = 50


def _safe_submenus_of(parent) -> list:
    """Return live submenus reachable from ``parent`` (a QMenuBar or
    QMenu). Wrappers whose underlying C++ object has been freed are
    skipped silently — see ``ImervueMainWindow._enable_tooltips_on_all_menus``.
    Mirrors the shiboken-teardown pattern in ``paint_workspace._safe_set_checked``."""
    out: list = []
    try:
        actions = parent.actions()
    except RuntimeError:
        return out
    for action in actions:
        try:
            submenu = action.menu()
        except RuntimeError:
            continue
        if submenu is not None:
            out.append(submenu)
    return out


def _any_tag_label() -> str:
    return language_wrapper.language_word_dict.get("image_filter_any_tag", "Any tag")


def _path_matches_image_filter(path: str, tokens: list[str]) -> bool:
    """Match simple folder filter tokens against one image path."""
    return all(_filter_token_matches(path, token) for token in tokens)


def _filter_token_matches(path: str, token: str) -> bool:
    if token.startswith("tag:"):
        from Imervue.user_settings.tags import get_tags_for_image
        wanted = token[4:].lower()
        return any(wanted in tag.lower() for tag in get_tags_for_image(path))
    if token.startswith("rating:"):
        return _rating_matches(path, token[7:])
    if token.startswith("date:"):
        return _date_matches(path, token[5:])
    return token.lower() in Path(path).name.lower()


def _date_matches(path: str, expr: str) -> bool:
    try:
        stamp = datetime.fromtimestamp(os.path.getmtime(path)).date().isoformat()
    except OSError:
        return False
    return stamp.startswith(expr)


class ImervueMainWindow(QMainWindow):
    def __init__(self, debug: bool = False):
        super().__init__()

        self.setWindowTitle("Imervue")
        self._set_app_user_model_id()
        # Accept image / folder drops anywhere on the window — not just
        # on the canvas — so artists can drop a file on the file tree
        # or status bar and have it open.
        self.setAcceptDrops(True)

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
        self._image_metadata_index = ImageMetadataIndex()
        self._folder_view_sessions: dict[str, dict] = dict(
            user_setting_dict.get("folder_view_sessions") or {}
        )
        self._restoring_filter_controls = False

        self.icon_path = _app_icon_path()
        self.icon = QIcon(str(self.icon_path))
        app = QApplication.instance()
        if app is not None and not self.icon.isNull():
            app.setWindowIcon(self.icon)
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
        # FolderThumbnailModel 供縮圖與檔案系統存取；FileTreeSortProxy 供
        # 具名排序鍵（含 QFileSystemModel 沒有欄位的「建立日期」），並轉發
        # QFileSystemModel 介面，所以其餘程式照舊把它當檔案系統 model 用。
        self.model = FileTreeSortProxy(FolderThumbnailModel())
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
        self.tree.set_thumbnail_size(
            user_setting_dict.get("tree_thumbnail_size", DEFAULT_ICON_SIZE))
        self.tree.setRootIndex(self.model.index(start_path))
        # 只顯示「名稱」欄，隱藏大小/類型/日期（省掉大量 stat() 呼叫）
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.header().setStretchLastSection(True)
        self.tree.setColumnWidth(0, 400)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(False)
        self.tree.clicked.connect(self.on_file_clicked)

        self.tree_search = QLineEdit()
        self.tree_search.setClearButtonEnabled(True)
        self.tree_search.setPlaceholderText(
            language_wrapper.language_word_dict.get(
                "tree_search_placeholder", "Search file tree...",
            ),
        )
        self.tree_search.textChanged.connect(self.tree.set_search_text)

        self._tree_panel = QWidget()
        tree_layout = QVBoxLayout(self._tree_panel)
        tree_layout.setContentsMargins(4, 4, 4, 4)
        tree_layout.setSpacing(4)
        tree_layout.addWidget(self.tree_search)
        tree_layout.addWidget(self.tree)

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
        self._tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._on_tab_context_menu)
        right_layout.addWidget(self._tab_bar)

        # ===== 麵包屑路徑列 =====
        from Imervue.gui.breadcrumb_bar import BreadcrumbBar
        self.breadcrumb = BreadcrumbBar(self)
        right_layout.addWidget(self.breadcrumb)

        right_layout.addWidget(self._build_filter_row())

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

        from Imervue.gui.image_issue_panel import ImageIssuePanel
        self.image_issue_panel = ImageIssuePanel(self)
        self._image_issue_dock = QDockWidget(
            language_wrapper.language_word_dict.get(
                "image_issues_title",
                "Image load issues",
            ),
            self,
        )
        self._image_issue_dock.setWidget(self.image_issue_panel)
        self._image_issue_dock.hide()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._image_issue_dock)

        self.viewer.on_filename_changed = self._on_viewer_filename_changed

        splitter.addWidget(self._tree_panel)
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

        # --------------------------------------------------------
        # Tab 2: Paint workspace — full-featured painting surface
        # --------------------------------------------------------
        from Imervue.paint.paint_workspace import PaintWorkspace
        self.paint_workspace = PaintWorkspace(parent=self)
        self._main_tabs.addTab(
            self.paint_workspace,
            lang.get("paint_tab_title", "Paint"),
        )

        # --------------------------------------------------------
        # Tab 3: Puppet workspace — 2D rigged-puppet animation.
        # Was a plugin; pulled in-tree as a built-in tab since the
        # core viewer / GL / mesh path runs on the default
        # requirements.txt. The Cubism Native SDK is the only
        # heavy optional dep and it gracefully unavailable when
        # the user hasn't supplied the DLL.
        # --------------------------------------------------------
        from Imervue.puppet import PuppetWorkspace
        self.puppet_workspace = PuppetWorkspace()
        self._main_tabs.addTab(
            self.puppet_workspace,
            lang.get("puppet_tab_title", "Puppet"),
        )

        # Desktop Pet tab + (optional) system tray.
        self._install_desktop_pet_tab(lang)

        # 切換分頁時把 viewer 移到正確的位置
        self._imervue_viewer_row = viewer_row
        self._main_tabs.currentChanged.connect(self._on_main_tab_changed)
        # On the Modify / Paint tabs, Left/Right should page images (like
        # DeepZoom) instead of the tab bar's default "switch tab". Filter the
        # tab bar's key events — it is the widget that holds focus after a tab
        # click and consumes the arrows.
        self._main_tabs.tabBar().installEventFilter(self)

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
        # VRAM tile-cache pressure indicator — green / yellow / red
        # dot + percentage. Polls the viewer; click clears the cache.
        from Imervue.gpu_image_view.memory_pressure import (
            MemoryPressureIndicator,
        )
        self._memory_pressure = MemoryPressureIndicator(
            source=self._collect_memory_pressure,
            clear_cache=self._on_memory_pressure_clear,
        )
        self._status_bar.addPermanentWidget(self._memory_pressure)
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

        # ===== What's New 自動彈出（升級後第一次啟動）=====
        # 延遲到主視窗顯示後再跑,避免遮住啟動畫面
        QTimer.singleShot(800, self._maybe_show_whats_new)

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
        self._folder_change_events = 0
        self._folder_change_last_path = ""
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

        # ===== 拖到別的螢幕 → 視窗與 deep-zoom 圖片自動適配 =====
        # moveEvent 在拖曳期間連續觸發；用單發計時器去抖動，等視窗
        # 「停下來」再檢查是否落在不同螢幕上（見 _adapt_to_current_screen）。
        self._screen_adapt_timer = QTimer(self)
        self._screen_adapt_timer.setSingleShot(True)
        self._screen_adapt_timer.setInterval(_SCREEN_ADAPT_DEBOUNCE_MS)
        self._screen_adapt_timer.timeout.connect(self._adapt_to_current_screen)
        self._last_screen_avail: tuple[int, int, int, int] | None = None
        self._screen_signal_connected = False

        # ===== 還原視窗位置與大小（多螢幕適配） =====
        self._restore_window_geometry()
        # Restoring geometry can jump the window from the primary screen it was
        # born on to a different monitor. Listen for that (and later drags) so
        # the view is re-fitted to the actual screen instead of keeping the
        # first screen's size. Deferred so windowHandle() exists.
        QTimer.singleShot(0, self._connect_screen_change_signal)

        # ===== Debug =====
        # Debug 模式下自動關閉
        # Auto close in debug mode
        if debug:
            self.debug_timer = QTimer()
            self.debug_timer.setInterval(10000)
            self.debug_timer.timeout.connect(self.debug_close)
            self.debug_timer.start()

    def _install_desktop_pet_tab(self, lang) -> None:
        """Wire the 5th tab (Desktop Pet) — frameless / transparent
        overlay sharing the Puppet runtime. The tab body is the
        control panel; the actual character lives in a separate
        top-level window. The system tray icon piggybacks here so
        the user can toggle visibility without finding the tab; it
        is only constructed when the platform reports a tray is
        available (CI / headless desktops skip it gracefully)."""
        from Imervue.desktop_pet import PetTrayIcon, PetWorkspace
        self.pet_workspace = PetWorkspace()
        self._main_tabs.addTab(
            self.pet_workspace,
            lang.get("desktop_pet_tab_title", "Desktop Pet"),
        )
        if not PetTrayIcon.is_available():
            return
        self._pet_tray = PetTrayIcon(self.pet_workspace, parent=self)
        self.pet_workspace.attach_tray(self._pet_tray)
        self._pet_tray.show()

    # ==========================
    # 主分頁切換（Imervue ↔ 修改）
    # ==========================
    def _collect_memory_pressure(self) -> dict:
        """Source callable for the status-bar memory-pressure widget.
        Returns the current ``(used, limit)`` byte counts plus a few
        cache-population numbers for the tooltip. Returns zeros when
        the viewer isn't ready yet so the widget shows ``--``."""
        viewer = getattr(self, "viewer", None)
        if viewer is None:
            return {"used_bytes": 0, "limit_bytes": 0}
        return {
            "used_bytes": int(getattr(viewer, "_vram_usage", 0)),
            "limit_bytes": int(getattr(viewer, "_vram_limit", 0)),
            "tile_count": len(getattr(viewer, "tile_textures", {})),
            "prefetch_count": len(getattr(viewer, "_prefetch_cache", {})),
        }

    def _on_memory_pressure_clear(self) -> None:
        """Click handler for the indicator. Drops the prefetch cache
        and the tile-texture cache so the user can recover the
        budget without restarting the app."""
        viewer = getattr(self, "viewer", None)
        if viewer is None:
            return
        cancel = getattr(viewer, "_cancel_all_prefetch", None)
        if callable(cancel):
            cancel()
        clear_tiles = getattr(viewer, "_delete_all_tile_textures", None)
        if callable(clear_tiles):
            clear_tiles()
        tile_cache = getattr(viewer, "tile_cache", None)
        if isinstance(tile_cache, dict):
            tile_cache.clear()

    def _on_main_tab_changed(self, idx: int) -> None:
        """Switch between Imervue (viewer), Modify and Paint tabs."""
        if idx == 1:
            # 切到修改分頁 → 綁定圖片，canvas 會自動插入 splitter 中間
            images = self.viewer.model.images
            path = None
            if images and 0 <= self.viewer.current_index < len(images):
                path = images[self.viewer.current_index]
            self.modify_panel.bind_to_path(path)
        elif idx == 2:
            # Paint 分頁 — 把目前圖片載入畫布
            self._bind_paint_workspace_to_current_image()
        else:
            # 切回 Imervue 主頁
            self.exif_sidebar.update_info()

    def _bind_paint_workspace_to_current_image(self) -> None:
        images = self.viewer.model.images
        if not images or not (0 <= self.viewer.current_index < len(images)):
            self.paint_workspace.load_image(None)
            return
        path = images[self.viewer.current_index]
        try:
            from PIL import Image
            import numpy as np
            with Image.open(path) as src:
                rgba = src.convert("RGBA")
                arr = np.array(rgba)
            self.paint_workspace.load_image(arr)
        except (OSError, ValueError):
            self.paint_workspace.load_image(None)

    def eventFilter(self, obj, event):
        """Route Left/Right on the Modify / Paint tab bars to image nav.

        On those tabs the default tab-switch is unwanted — the user wants the
        arrows to page images like the browse view. Every other tab / key
        falls through to Qt's default handling.
        """
        from PySide6.QtCore import QEvent, Qt
        if (obj is self._main_tabs.tabBar()
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
        """Page the viewer's current image and reload it into the paint canvas."""
        from Imervue.gpu_image_view.actions.select import (
            switch_to_next_image,
            switch_to_previous_image,
        )
        if direction > 0:
            switch_to_next_image(main_gui=self.viewer)
        else:
            switch_to_previous_image(main_gui=self.viewer)
        self._bind_paint_workspace_to_current_image()

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
        # QMenu hides per-action tooltips by default; enable on every
        # top-level menu so any setToolTip() on its actions surfaces
        # on hover. Walks the bar once at construction time so future
        # builders don't have to remember the flag.
        self._enable_tooltips_on_all_menus()

    def _enable_tooltips_on_all_menus(self) -> None:
        """Enable per-action tooltips on every top-level menu and any
        submenus reachable from them. Safe to call repeatedly — Qt's
        ``setToolTipsVisible`` is idempotent. Defensive against shiboken
        wrappers whose C++ peer has been freed; skipping them costs at
        most one menu's tooltip flag, missing them aborts startup."""
        bar = self.menuBar()
        if bar is None:
            return
        seen: set[int] = set()
        pending: list[QMenu] = list(_safe_submenus_of(bar))
        while pending:
            menu = pending.pop()
            if id(menu) in seen:
                continue
            seen.add(id(menu))
            try:
                menu.setToolTipsVisible(True)
            except RuntimeError:
                continue
            pending.extend(_safe_submenus_of(menu))

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
            # If viewer was sitting on tile grid, re-render it fresh. The wall
            # renders straight from the tile cache with no per-tile lazy refill,
            # so reload it whenever the cache no longer covers the folder
            # (otherwise it would show blank placeholders).
            if self.viewer.model.images and not self.viewer.deep_zoom:
                from Imervue.gpu_image_view.tile_loader import tile_grid_needs_reload
                if tile_grid_needs_reload(self.viewer.tile_cache, self.viewer.model.images):
                    self.viewer.load_tile_grid_async(list(self.viewer.model.images))
                else:
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
        self.image_list_view.set_paths(
            list(self.viewer.model.images),
            metadata_index=getattr(self, "_image_metadata_index", None),
        )

    def _build_filter_row(self) -> QWidget:
        """Build the filename/tag/rating/date filter bar above the viewer."""
        filter_row = QWidget()
        filter_layout = QHBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)

        self.image_filter = QLineEdit()
        self.image_filter.setClearButtonEnabled(True)
        self.image_filter.setPlaceholderText(
            language_wrapper.language_word_dict.get(
                "image_filter_filename_placeholder",
                "Filename",
            ),
        )
        self.image_filter.textChanged.connect(self._on_image_filter_changed)
        filter_layout.addWidget(self.image_filter, stretch=2)

        self.tag_filter = QComboBox()
        self.tag_filter.setEditable(True)
        self.tag_filter.setMinimumWidth(120)
        self.tag_filter.addItem(_any_tag_label(), "")
        self.tag_filter.currentTextChanged.connect(self._on_image_filter_changed)
        filter_layout.addWidget(self.tag_filter, stretch=1)

        self.rating_filter = QComboBox()
        self.rating_filter.setMinimumWidth(110)
        self.rating_filter.addItem(
            language_wrapper.language_word_dict.get("image_filter_any_rating", "Any rating"),
            "",
        )
        for rating in range(1, 6):
            self.rating_filter.addItem(f">= {rating}", f">={rating}")
        self.rating_filter.currentIndexChanged.connect(self._on_image_filter_changed)
        filter_layout.addWidget(self.rating_filter, stretch=0)

        self.date_from_filter = QLineEdit()
        self.date_from_filter.setClearButtonEnabled(True)
        self.date_from_filter.setPlaceholderText(
            language_wrapper.language_word_dict.get("image_filter_date_from", "From date"),
        )
        self.date_from_filter.textChanged.connect(self._on_image_filter_changed)
        filter_layout.addWidget(self.date_from_filter, stretch=1)

        self.date_to_filter = QLineEdit()
        self.date_to_filter.setClearButtonEnabled(True)
        self.date_to_filter.setPlaceholderText(
            language_wrapper.language_word_dict.get("image_filter_date_to", "To date"),
        )
        self.date_to_filter.textChanged.connect(self._on_image_filter_changed)
        filter_layout.addWidget(self.date_to_filter, stretch=1)

        self.missing_batch_button = QPushButton(
            language_wrapper.language_word_dict.get("missing_batch_menu", "Missing"),
        )
        self.missing_batch_button.clicked.connect(self._show_missing_batch_menu)
        filter_layout.addWidget(self.missing_batch_button, stretch=0)
        return filter_row

    def _on_viewer_filename_changed(self, name) -> None:
        base_template = language_wrapper.language_word_dict.get(
            "main_window_current_filename_format",
        ).format(name=name)
        # Append "(i/n)" position info when the viewer knows its
        # spot in the folder so the user can pace their browsing
        # without hunting through the file list. Keep the
        # baseline label so any locale that already localised
        # the prefix stays untouched.
        extras: list[str] = []
        with contextlib.suppress(Exception):
            images = self.viewer.model.images or []
            idx = self.viewer.current_index
            if 0 <= idx < len(images):
                extras.append(f"({idx + 1}/{len(images)})")
        self.filename_label.setText(
            base_template + ("  " + " ".join(extras) if extras else ""),
        )
        self.exif_sidebar.update_info()
        # Keep the tab bar in lockstep with whatever image the viewer
        # now shows. Only sync in deep-zoom mode — tile grid / folder
        # browsing intentionally doesn't create tabs.
        with contextlib.suppress(Exception):
            images = self.viewer.model.images
            idx = self.viewer.current_index
            if self.viewer.deep_zoom and 0 <= idx < len(images):
                self._sync_current_tab_with_path(images[idx])

    def _on_image_filter_changed(self, *_args) -> None:
        if getattr(self, "_restoring_filter_controls", False):
            return
        self._apply_image_filter()
        self._save_current_folder_session()

    def _apply_image_filter(self, text: str | None = None) -> None:
        """Filter the current folder by filename/tag/rating/date immediately."""
        base = list(getattr(self.viewer, "_unfiltered_images", None) or self.viewer.model.images)
        if text is None:
            spec = self._current_filter_spec()
            filtered = filter_paths(base, spec, self._image_metadata_index)
        else:
            filtered = self._filter_image_paths(base, text)
        current = self.viewer._current_path()
        if self.viewer.tile_grid_mode:
            from Imervue.gpu_image_view.tile_loader import sync_tile_grid_incremental
            sync_tile_grid_incremental(self.viewer, filtered)
        else:
            self.viewer.model.set_images(filtered)
        if current in filtered:
            self.viewer.current_index = filtered.index(current)
        elif filtered:
            self.viewer.current_index = 0
        else:
            self.viewer.current_index = 0
        self.refresh_list_view()
        self.viewer.update()

    def _current_filter_spec(self) -> ImageFilterSpec:
        tag = ""
        if hasattr(self, "tag_filter"):
            tag = self.tag_filter.currentData() or self.tag_filter.currentText()
            if tag == _any_tag_label():
                tag = ""
        rating = ""
        if hasattr(self, "rating_filter"):
            rating = self.rating_filter.currentData() or ""
        return ImageFilterSpec(
            filename=self.image_filter.text() if hasattr(self, "image_filter") else "",
            tag=str(tag or ""),
            rating=str(rating or ""),
            date_from=self._parse_filter_date(
                self.date_from_filter.text() if hasattr(self, "date_from_filter") else "",
            ),
            date_to=self._parse_filter_date(
                self.date_to_filter.text() if hasattr(self, "date_to_filter") else "",
            ),
        )

    @staticmethod
    def _parse_filter_date(value: str) -> date | None:
        value = (value or "").strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _filter_state(self) -> dict:
        return {
            "filename": self.image_filter.text() if hasattr(self, "image_filter") else "",
            "tag": self.tag_filter.currentData() if hasattr(self, "tag_filter") else "",
            "rating": self.rating_filter.currentData() if hasattr(self, "rating_filter") else "",
            "date_from": self.date_from_filter.text() if hasattr(self, "date_from_filter") else "",
            "date_to": self.date_to_filter.text() if hasattr(self, "date_to_filter") else "",
        }

    def _restore_filter_state(self, state: dict | None) -> None:
        if not state:
            state = {}
        self._restoring_filter_controls = True
        try:
            if hasattr(self, "image_filter"):
                self.image_filter.setText(str(state.get("filename") or ""))
            if hasattr(self, "tag_filter"):
                tag = str(state.get("tag") or "")
                idx = self.tag_filter.findData(tag)
                if idx >= 0:
                    self.tag_filter.setCurrentIndex(idx)
                else:
                    self.tag_filter.setEditText(tag)
            if hasattr(self, "rating_filter"):
                rating = str(state.get("rating") or "")
                idx = self.rating_filter.findData(rating)
                self.rating_filter.setCurrentIndex(max(idx, 0))
            if hasattr(self, "date_from_filter"):
                self.date_from_filter.setText(str(state.get("date_from") or ""))
            if hasattr(self, "date_to_filter"):
                self.date_to_filter.setText(str(state.get("date_to") or ""))
        finally:
            self._restoring_filter_controls = False

    def _refresh_tag_filter_options(self) -> None:
        if not hasattr(self, "tag_filter"):
            return
        from Imervue.user_settings.tags import get_all_tags
        current = self.tag_filter.currentData() or self.tag_filter.currentText() or ""
        self._restoring_filter_controls = True
        try:
            self.tag_filter.clear()
            self.tag_filter.addItem(_any_tag_label(), "")
            for tag in sorted(get_all_tags()):
                self.tag_filter.addItem(tag, tag)
            idx = self.tag_filter.findData(current)
            if idx >= 0:
                self.tag_filter.setCurrentIndex(idx)
            elif current:
                self.tag_filter.setEditText(str(current))
        finally:
            self._restoring_filter_controls = False

    def _show_missing_batch_menu(self) -> None:
        if not hasattr(self, "missing_batch_button"):
            return
        lang = language_wrapper.language_word_dict
        menu = QMenu(self)
        scan_action = menu.addAction(
            lang.get("missing_batch_scan_same_name", "Auto-match same-name files"),
        )
        remove_action = menu.addAction(
            lang.get("missing_batch_remove", "Remove missing from view"),
        )
        relocate_action = menu.addAction(
            lang.get("missing_batch_relocate_root", "Relocate root folder..."),
        )
        chosen = menu.exec(self.missing_batch_button.mapToGlobal(
            self.missing_batch_button.rect().bottomLeft(),
        ))
        if chosen is scan_action:
            self._batch_auto_match_missing()
        elif chosen is remove_action:
            self._batch_remove_missing()
        elif chosen is relocate_action:
            self._batch_relocate_root()

    def _missing_candidates(self) -> list[str]:
        paths = []
        paths.extend(getattr(self.viewer, "_unfiltered_images", []) or [])
        paths.extend(getattr(getattr(self.viewer, "model", None), "images", []) or [])
        if getattr(self.viewer, "_deep_zoom_error", None):
            paths.append(self.viewer._deep_zoom_error[0])
        seen = set()
        unique = []
        for path in paths:
            if path and path not in seen:
                seen.add(path)
                unique.append(path)
        return missing_paths(unique)

    def _batch_auto_match_missing(self) -> None:
        folder = self._current_view_folder()
        mapping = auto_match_same_name(self._missing_candidates(), folder)
        self._apply_missing_replacements(mapping)

    def _batch_remove_missing(self) -> None:
        base = list(getattr(self.viewer, "_unfiltered_images", None) or self.viewer.model.images)
        kept = remove_missing(base)
        removed = len(base) - len(kept)
        self.viewer._unfiltered_images = kept
        offline = getattr(self.viewer, "offline_paths", None)
        if isinstance(offline, set):
            offline.intersection_update(set(kept))
        if hasattr(self.viewer, "tile_errors"):
            self.viewer.tile_errors = {
                path: msg for path, msg in getattr(self.viewer, "tile_errors", {}).items()
                if path in kept
            }
        self._apply_image_filter()
        self._toast_missing_result("missing_batch_removed_done", removed)

    def _batch_relocate_root(self) -> None:
        missing = self._missing_candidates()
        if not missing:
            self._toast_missing_result("missing_batch_none", 0)
            return
        from PySide6.QtWidgets import QFileDialog
        lang = language_wrapper.language_word_dict
        new_root = QFileDialog.getExistingDirectory(
            self,
            lang.get("missing_batch_relocate_root", "Relocate root folder..."),
            str(Path(missing[0]).parent),
        )
        if not new_root:
            return
        old_root = self._common_missing_root(missing)
        self._apply_missing_replacements(relocate_root(missing, old_root, new_root))

    @staticmethod
    def _common_missing_root(paths: list[str]) -> str:
        parents = [str(Path(path).parent) for path in paths]
        try:
            return os.path.commonpath(parents)
        except ValueError:
            return parents[0] if parents else ""

    def _apply_missing_replacements(self, mapping: dict[str, str]) -> None:
        if not mapping:
            self._toast_missing_result("missing_batch_none", 0)
            return
        viewer = self.viewer
        migrate_view_path_state(viewer, mapping)
        for old, new in mapping.items():
            self._image_metadata_index.move(old, new)
            self._migrate_user_path_metadata(old, new)
        for attr in ("_unfiltered_images",):
            paths = list(getattr(viewer, attr, []) or [])
            setattr(viewer, attr, [mapping.get(path, path) for path in paths])
        if getattr(viewer, "model", None) is not None:
            viewer.model.set_images([mapping.get(path, path) for path in viewer.model.images])
        if getattr(viewer, "_deep_zoom_error", None):
            old_path, _ = viewer._deep_zoom_error
            if old_path in mapping:
                viewer._deep_zoom_error = None
                viewer.load_deep_zoom_image(mapping[old_path])
        self._apply_image_filter()
        self._toast_missing_result("missing_batch_relinked_done", len(mapping))

    @staticmethod
    def _migrate_user_path_metadata(old_path: str, new_path: str) -> None:
        ratings = user_setting_dict.get("image_ratings")
        if isinstance(ratings, dict) and old_path in ratings and new_path not in ratings:
            ratings[new_path] = ratings.pop(old_path)
        tags = user_setting_dict.get("image_tags")
        if isinstance(tags, dict):
            for paths in tags.values():
                if isinstance(paths, list) and old_path in paths and new_path not in paths:
                    paths[paths.index(old_path)] = new_path

    def _toast_missing_result(self, key: str, count: int) -> None:
        if not hasattr(self, "toast"):
            return
        lang = language_wrapper.language_word_dict
        fallback = {
            "missing_batch_none": "No missing files matched",
            "missing_batch_removed_done": "Removed {n} missing file(s)",
            "missing_batch_relinked_done": "Relinked {n} missing file(s)",
        }.get(key, "{n}")
        msg = lang.get(key, fallback).format(n=count)
        if count:
            self.toast.success(msg)
        else:
            self.toast.info(msg)

    def record_image_issue(self, path: str, message: str) -> None:
        panel = getattr(self, "image_issue_panel", None)
        if panel is not None:
            panel.add_issue(path, message)

    def clear_image_issue(self, path: str) -> None:
        panel = getattr(self, "image_issue_panel", None)
        if panel is not None:
            panel.clear_issue(path)

    @staticmethod
    def _filter_image_paths(paths: list[str], query: str) -> list[str]:
        return filter_paths(paths, ImageFilterSpec(raw_query=query))

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

    def change_tile_size(self, size):
        # Delegate to the viewer, which keeps the user in deep zoom (instead of
        # dropping back to the wall and wiping the status bar) when a size is
        # picked mid-zoom. See ``GPUImageView.set_thumbnail_size``.
        self.viewer.set_thumbnail_size(size)

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
        """Coalesce folder-change bursts into one stable refresh."""
        self._folder_change_events += 1
        self._folder_change_last_path = _path
        self._folder_refresh_timer.start(1200 if self._folder_change_events >= 8 else 500)

    def _do_folder_refresh(self):
        """去抖動後重新掃描資料夾並更新 tile grid"""
        self._folder_change_events = 0
        viewer = self.viewer
        folder = self._current_view_folder()
        if not folder:
            return
        if not Path(folder).is_dir():
            self._handle_active_folder_missing(folder)
            return

        from Imervue.gpu_image_view.images.image_loader import _scan_images_for_user
        new_images = _scan_images_for_user(folder)
        self._image_metadata_index.prime(new_images, limit=512)

        current_full = list(getattr(viewer, "_unfiltered_images", None) or viewer.model.images)
        if new_images != current_full:
            self._apply_refreshed_image_list(new_images)

    def _current_view_folder(self) -> str:
        """Folder backing the current viewer state, if any."""
        images = self.viewer.model.images
        if images:
            return str(Path(images[0]).parent)
        dirs = self._folder_watcher.directories()
        return dirs[0] if dirs else ""

    def _save_current_folder_session(self) -> None:
        folder = self._current_view_folder()
        if not folder:
            return
        viewer = self.viewer
        scroll = 0
        if self._browse_mode == "list" and hasattr(self, "image_list_view"):
            with contextlib.suppress(Exception):
                scroll = self.image_list_view.verticalScrollBar().value()
        elif hasattr(viewer, "scroll_y"):
            scroll = int(getattr(viewer, "scroll_y", 0))
        self._folder_view_sessions[folder] = {
            "filter": self._filter_state(),
            "browse_mode": self._browse_mode,
            "scroll": scroll,
            "selected": list(getattr(viewer, "selected_tiles", set())),
            "current": viewer._current_path() if hasattr(viewer, "_current_path") else "",
            "deep_zoom": bool(
                getattr(viewer, "deep_zoom", None) is not None
                and not getattr(viewer, "tile_grid_mode", False)
            ),
        }
        user_setting_dict["folder_view_sessions"] = self._folder_view_sessions
        write_user_setting()

    def _restore_folder_session(self, folder: str) -> None:
        state = self._folder_view_sessions.get(folder) or {}
        self._restore_filter_state(state.get("filter") or {})
        selected = set(state.get("selected") or [])
        if isinstance(getattr(self.viewer, "selected_tiles", None), set):
            self.viewer.selected_tiles.clear()
            self.viewer.selected_tiles.update(
                path for path in selected if path in self.viewer.model.images
            )
        current = state.get("current") or ""
        if current in self.viewer.model.images:
            self.viewer.current_index = self.viewer.model.images.index(current)
        self._apply_image_filter()
        if state.get("browse_mode") in {"grid", "list"}:
            self.set_browse_mode(state["browse_mode"])
        scroll = int(state.get("scroll") or 0)
        if self._browse_mode == "list" and hasattr(self, "image_list_view"):
            QTimer.singleShot(0, lambda: self.image_list_view.verticalScrollBar().setValue(scroll))
        elif hasattr(self.viewer, "scroll_y"):
            self.viewer.scroll_y = scroll

    def _restore_deep_zoom_if_saved(self, state: dict, _retries: int = 60) -> None:
        """Re-enter deep zoom on the remembered image after a startup restore.

        The folder scan fills ``model.images`` asynchronously, so the target
        may not exist yet on the first pass; retry (bounded) until it lands,
        then open it in deep zoom. Running after the scan also means the window
        has reached its restored size, so the fit is correct. Startup-only (not
        folder navigation), so browsing the tree still lands on the tile wall.
        """
        from Imervue.sessions.folder_session import (
            deep_zoom_restore_target,
            should_retry_deep_zoom_restore,
        )
        viewer = self.viewer
        target = deep_zoom_restore_target(state, viewer.model.images)
        if target is not None:
            viewer.current_index = viewer.model.images.index(target)
            viewer.tile_grid_mode = False
            viewer.load_deep_zoom_image(target)
            return
        if _retries > 0 and should_retry_deep_zoom_restore(state, viewer.model.images):
            QTimer.singleShot(
                _DEEP_ZOOM_RESTORE_RETRY_MS,
                lambda: self._restore_deep_zoom_if_saved(state, _retries - 1),
            )

    def _handle_active_folder_missing(self, folder: str) -> None:
        """Reset viewer chrome when the folder currently being browsed is gone."""
        viewer = self.viewer
        viewer._unfiltered_images = []
        viewer.load_tile_grid_async([])
        viewer.current_index = 0
        if self._browse_mode == "list":
            self.refresh_list_view()
            self._view_stack.setCurrentIndex(1)
        else:
            self._view_stack.setCurrentIndex(0)

        parent = self._nearest_existing_parent(Path(folder))
        if parent:
            self.model.setRootPath(parent)
            self.tree.setRootIndex(self.model.index(parent))
            self._clear_view_folder_watch()
            if hasattr(self, "_tree_watchdog"):
                self._tree_watchdog.watch(parent)
            self.breadcrumb.set_path(parent)
        else:
            self.watch_folder("")

        lang = language_wrapper.language_word_dict
        self.filename_label.setText(
            lang.get(
                "main_window_folder_missing",
                "Folder no longer exists: {path}",
            ).format(path=folder),
        )
        if hasattr(self, "toast"):
            self.toast.warning(
                lang.get(
                    "folder_removed",
                    "Folder was removed: {name}",
                ).format(name=Path(folder).name or folder),
            )

    def _clear_view_folder_watch(self) -> None:
        """Stop the viewer folder watcher without changing the file-tree root."""
        watcher = getattr(self, "_folder_watcher", None)
        if watcher is None:
            return
        dirs = watcher.directories()
        if dirs:
            watcher.removePaths(dirs)

    @staticmethod
    def _nearest_existing_parent(path: Path) -> str:
        """Return the nearest existing parent folder for a removed path."""
        for candidate in (path.parent, *path.parents):
            if candidate and candidate.is_dir():
                return str(candidate)
        return ""

    def _apply_refreshed_image_list(self, new_images: list[str]) -> None:
        """Update tile/list/deep-zoom state after an external folder change."""
        viewer = self.viewer
        old_images = list(viewer.model.images)
        old_full = list(getattr(viewer, "_unfiltered_images", None) or old_images)
        rename_map = detect_renamed_paths(old_full, new_images, self._image_metadata_index)
        if rename_map:
            migrate_view_path_state(viewer, rename_map)
            for old, new in rename_map.items():
                self._image_metadata_index.move(old, new)
        old_index = viewer.current_index
        current_path = (
            old_images[old_index]
            if 0 <= old_index < len(old_images) else None
        )
        current_path = rename_map.get(current_path, current_path)

        if not new_images:
            viewer._unfiltered_images = []
            viewer.load_tile_grid_async([])
            viewer.current_index = 0
            if self._browse_mode == "list":
                self.refresh_list_view()
            return

        viewer._unfiltered_images = list(new_images)
        self._image_metadata_index.prime(new_images, limit=512)
        self._refresh_tag_filter_options()
        filtered_images = filter_paths(
            new_images,
            self._current_filter_spec(),
            self._image_metadata_index,
        )

        if viewer.tile_grid_mode:
            from Imervue.gpu_image_view.tile_loader import sync_tile_grid_incremental
            sync_tile_grid_incremental(viewer, filtered_images)
            return

        viewer.model.set_images(filtered_images)
        if current_path in filtered_images:
            viewer.current_index = filtered_images.index(current_path)
            self.refresh_list_view()
            viewer.update()
            return

        if viewer.deep_zoom is not None and filtered_images:
            viewer.current_index = min(old_index, len(filtered_images) - 1)
            viewer._clear_deep_zoom()
            viewer.tile_grid_mode = False
            viewer.load_deep_zoom_image(filtered_images[viewer.current_index])
        else:
            viewer.current_index = (
                min(old_index, len(filtered_images) - 1)
                if filtered_images else 0
            )
            self.refresh_list_view()
            viewer.update()

    # ==========================
    # 點擊檔案
    # ==========================
    def on_file_clicked(self, index):
        self.navigate_to_path(self.model.filePath(index))

    def navigate_to_path(self, path: str) -> None:
        """Open a folder (tile grid) or a file (deep zoom) and sync the chrome.

        The single entry point the file tree AND the breadcrumb both call, so
        navigation is identical from either: same root, viewer reset, path bar,
        folder watch and recent menu. (The breadcrumb used to duplicate this and
        drifted — it stopped updating the path bar.)
        """
        if Path(path).is_dir():
            # 點擊資料夾 → 導航進入並載入圖片
            self._save_current_folder_session()
            self.model.setRootPath(path)
            self.tree.setRootIndex(self.model.index(path))
            self.viewer.clear_tile_grid()
            open_path(main_gui=self.viewer, path=path)
            self._image_metadata_index.prime(
                getattr(self.viewer, "_unfiltered_images", self.viewer.model.images),
                limit=512,
            )
            self._refresh_tag_filter_options()
            self._restore_folder_session(path)
            self.filename_label.setText(
                language_wrapper.language_word_dict.get(
                    "main_window_current_folder_format"
                ).format(path=path)
            )
            self.breadcrumb.set_path(path)
            self.watch_folder(path)
        elif Path(path).is_file():
            self._save_current_folder_session()
            self.viewer.clear_tile_grid()
            open_path(main_gui=self.viewer, path=path)
            self.breadcrumb.set_path(str(Path(path).parent))

        rebuild_recent_menu(self)

    def _on_directory_loaded(self, directory: str):
        """QFileSystemModel 目錄載入完成回調，確保樹狀圖正確顯示"""
        idx = self.model.index(directory)
        if idx.isValid():
            self.tree.update(idx)

    def _maybe_show_whats_new(self) -> None:
        """Pop up the What's New dialog if the user just upgraded.

        Also runs the onboarding tour on first launch — both checks are
        cheap when not triggered, and we want exactly one auto-popup
        flow at startup so the two play together rather than racing.
        """
        try:
            from Imervue.gui.onboarding_dialog import show_onboarding_if_first_run
            from Imervue.gui.whats_new_dialog import show_whats_new_if_upgraded
        except ImportError:
            return
        with contextlib.suppress(Exception):
            shown = show_onboarding_if_first_run(self)
            if not shown:
                show_whats_new_if_upgraded(self)

    def _on_clipboard_image_captured(self, pil_image) -> None:
        """Open the annotation dialog when the clipboard monitor sees a new image."""
        from Imervue.gui.annotation_dialog import open_annotation_for_clipboard_image
        try:
            open_annotation_for_clipboard_image(self, pil_image)
        except Exception:
            import logging
            logging.getLogger("Imervue").exception("clipboard annotation dialog failed")

    def _set_app_user_model_id(self) -> None:
        """Tag the process with an AppUserModelID so Windows shows the
        right icon / groups taskbar entries. Silently no-op everywhere
        else (Linux / macOS lack the ctypes shell32 surface)."""
        self.id = "Imervue"
        try:
            from ctypes import windll
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.id)
        except (ImportError, AttributeError):
            pass

    def _open_startup_folder(self, folder: str):
        self.model.setRootPath(folder)
        self.tree.setRootIndex(self.model.index(folder))
        open_path(main_gui=self.viewer, path=folder)
        self._image_metadata_index.prime(
            getattr(self.viewer, "_unfiltered_images", self.viewer.model.images),
            limit=512,
        )
        self._refresh_tag_filter_options()
        self._restore_folder_session(folder)
        # Startup-only: reopen the last deep-zoom image if the session recorded
        # one, so relaunching returns to where the user left off.
        self._restore_deep_zoom_if_saved(self._folder_view_sessions.get(folder) or {})
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

    def _on_tab_context_menu(self, pos) -> None:
        """Right-click on a tab → reveal / copy path / close family."""
        idx = self._tab_bar.tabAt(pos)
        if idx < 0:
            return
        lang = language_wrapper.language_word_dict
        menu = QMenu(self._tab_bar)
        tab_path = self._image_tabs[idx].get("path", "") if 0 <= idx < len(self._image_tabs) else ""

        reveal_act = None
        copy_path_act = None
        if tab_path:
            reveal_act = menu.addAction(
                lang.get("tab_reveal_in_tree", "Reveal in File Tree"),
            )
            copy_path_act = menu.addAction(lang.get("tab_copy_path", "Copy Path"))
            menu.addSeparator()

        close_act = menu.addAction(lang.get("tab_close", "Close"))
        close_others = menu.addAction(lang.get("tab_close_others", "Close Other Tabs"))
        close_right = menu.addAction(
            lang.get("tab_close_to_right", "Close Tabs to the Right"),
        )
        menu.addSeparator()
        close_all = menu.addAction(lang.get("tab_close_all", "Close All Tabs"))
        chosen = menu.exec(self._tab_bar.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is reveal_act:
            self._reveal_path_in_tree(tab_path)
        elif chosen is copy_path_act:
            QApplication.clipboard().setText(tab_path)
        elif chosen is close_act:
            self._on_tab_close(idx)
        elif chosen is close_others:
            self._close_tabs_except(idx)
        elif chosen is close_right:
            self._close_tabs_after(idx)
        elif chosen is close_all:
            self._close_all_tabs()

    def _reveal_path_in_tree(self, path: str) -> None:
        """Scroll the file tree to ``path`` and select that row, so the
        user has a one-click bridge from "this tab's image" back to its
        location on disk. Falls back silently if the path is gone."""
        if not path:
            return
        if not Path(path).exists():
            if hasattr(self, "toast"):
                lang = language_wrapper.language_word_dict
                self.toast.warning(
                    lang.get(
                        "tab_reveal_missing", "{name} is no longer on disk",
                    ).format(name=Path(path).name or path),
                )
            return
        index = self.model.index(path)
        if not index.isValid():
            return
        self.tree.scrollTo(index)
        self.tree.setCurrentIndex(index)
        self.tree.setFocus()

    def _close_tabs_except(self, keep_idx: int) -> None:
        """Close every tab whose index is not ``keep_idx``."""
        if not (0 <= keep_idx < len(self._image_tabs)):
            return
        # Walk highest-to-lowest so popping doesn't shift the kept index.
        for idx in reversed(range(len(self._image_tabs))):
            if idx != keep_idx:
                self._on_tab_close(idx)

    def _close_tabs_after(self, idx: int) -> None:
        """Close every tab whose index is greater than ``idx``."""
        for closing in reversed(range(idx + 1, len(self._image_tabs))):
            self._on_tab_close(closing)

    def _close_all_tabs(self) -> None:
        for idx in reversed(range(len(self._image_tabs))):
            self._on_tab_close(idx)

    # ===== Drag-and-drop on the main window =====

    _SUPPORTED_DROP_EXTS = (
        ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp",
        ".gif", ".apng", ".svg",
        ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf",
    )

    @classmethod
    def _is_supported_drop(cls, path: str) -> bool:
        """Return True iff the dropped path is a folder or an image with
        a recognised extension."""
        p = Path(path)
        if p.is_dir():
            return True
        return p.suffix.lower() in cls._SUPPORTED_DROP_EXTS

    def dragEnterEvent(self, event):  # noqa: N802 — Qt naming
        urls = event.mimeData().urls() if event.mimeData() else []
        if any(self._is_supported_drop(u.toLocalFile()) for u in urls if u.isLocalFile()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802 — Qt naming
        urls = event.mimeData().urls() if event.mimeData() else []
        for url in urls:
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if self._is_supported_drop(path):
                self._open_dropped_path(path)
                event.acceptProposedAction()
                return
        event.ignore()

    def _open_dropped_path(self, path: str) -> None:
        """Open a dropped file or folder via the viewer's existing
        load path. Folders re-root the file tree; image files load
        into the deep-zoom viewer."""
        target = Path(path)
        if target.is_dir():
            self._open_startup_folder(str(target))
            return
        if target.is_file():
            try:
                open_path(main_gui=self.viewer, path=str(target))
            except Exception:   # noqa: BLE001 — load surface raises a wide variety
                logger = logging.getLogger("Imervue")
                logger.exception("drop-load failed: %s", target)
                if hasattr(self, "toast"):
                    lang = language_wrapper.language_word_dict
                    self.toast.error(
                        lang.get("drop_load_failed", "Couldn't open {name}").format(
                            name=target.name,
                        ),
                    )

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
    # 拖到別的螢幕 → 自動適配
    # ==========================
    def moveEvent(self, event):  # noqa: N802 — Qt naming
        super().moveEvent(event)
        # __init__ 還沒跑完前 Qt 就可能送出第一個 moveEvent。
        timer = getattr(self, "_screen_adapt_timer", None)
        if timer is not None:
            timer.start()

    def _connect_screen_change_signal(self) -> None:
        """Subscribe to the window's screen-changed signal exactly once."""
        if self._screen_signal_connected:
            return
        handle = self.windowHandle()
        if handle is None:
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
                self.modify_panel._size_modify_splitter(splitter)
            QTimer.singleShot(0, canvas.update)

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

        Deferred one event-loop turn so the fit math sees the canvas size
        AFTER the ``setGeometry`` layout pass, not the mid-resize one.
        Intentionally overrides a user zoom/pan — landing on a new screen
        means "show me the whole image at this screen's size".
        """
        viewer = self.viewer
        if viewer.deep_zoom is None or viewer.tile_grid_mode:
            return

        def _do_fit() -> None:
            if viewer.deep_zoom is not None and not viewer.tile_grid_mode:
                viewer._fit_to_window()
                viewer.update()

        QTimer.singleShot(0, _do_fit)

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

    def closeEvent(self, event):
        import logging
        logging.getLogger("Imervue").info("closeEvent triggered")

        # Snapshot the current folder's view state (incl. whether we're in deep
        # zoom) BEFORE any teardown clears the viewer, so relaunching can return
        # to where the user left off instead of always to the tile wall.
        with contextlib.suppress(Exception):
            self._save_current_folder_session()

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
