import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QMenu, QTabWidget,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget

from Imervue.system.qt_timers import call_later
from Imervue.image.formats import VIEWER_EXTENSIONS
from Imervue.system.app_paths import icon_path as _app_icon_path
from Imervue.system.best_effort import best_effort
from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.gui.file_tree_view import _FileTreeView, _next_duplicate_name  # noqa: F401  # _next_duplicate_name re-exported for tests
from Imervue.gui.toast import ToastManager
from Imervue.image.browser_state import (
    ImageMetadataIndex,
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
import weakref
from Imervue.gui.main_window_filter import MainWindowFilterMixin
from Imervue.gui.main_window_missing import MainWindowMissingMixin
from Imervue.gui.main_window_folders import MainWindowFoldersMixin
from Imervue.gui.main_window_tabs import MainWindowTabsMixin
from Imervue.gui.main_window_layout import MainWindowLayoutMixin
from Imervue.gui.main_window_screens import MainWindowScreensMixin
from Imervue.gui.main_window_views import MainWindowViewsMixin
from Imervue.gui.main_window_status import MainWindowStatusMixin
from Imervue.gui.main_window_browse import MainWindowBrowseMixin

# 拖曳視窗時 moveEvent 連續觸發；停止移動這麼久後才檢查螢幕是否改變。
_SCREEN_ADAPT_DEBOUNCE_MS = 300


_logger = logging.getLogger("Imervue.main_window")

def _other_live_windows_remain(registry, closing) -> bool:
    """True if any live main window other than *closing* is still registered.

    Pure so the last-window decision behind the ``os._exit`` on close can be
    unit-tested with plain objects (``QApplication.topLevelWidgets`` /
    ``isinstance`` are not fake-friendly)."""
    return any(window is not closing for window in registry)


class ImervueMainWindow(
        MainWindowLayoutMixin, MainWindowBrowseMixin, MainWindowStatusMixin, MainWindowViewsMixin,
        MainWindowScreensMixin, MainWindowTabsMixin, MainWindowFoldersMixin,
        MainWindowMissingMixin, MainWindowFilterMixin, QMainWindow):
    # Every live main window registers here so closeEvent can tell whether it is
    # the LAST one. File -> New Window opens a second instance that shares this
    # closeEvent; without the check, closing any one window ran the app-global
    # plugin unload + os._exit and killed the whole process.
    _live_windows: "weakref.WeakSet[ImervueMainWindow]" = weakref.WeakSet()

    def __init__(self, debug: bool = False):
        super().__init__()
        ImervueMainWindow._live_windows.add(self)

        self.setWindowTitle("Imervue")
        self._set_app_user_model_id()
        # Accept image / folder drops anywhere on the window — not just
        # on the canvas — so artists can drop a file on the file tree
        # or status bar and have it open.
        self.setAcceptDrops(True)

        read_user_setting()
        last_folder = user_setting_dict.get("user_last_folder", "")

        if last_folder and Path(last_folder).is_dir():
            call_later(0, self, lambda: self._open_startup_folder(last_folder))

        self._init_language_and_icon()

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

        self._build_file_tree()

        right_widget = self._build_viewer_column()

        # ===== 組裝 Tab 0：檔案樹 | 檢視器欄 =====
        splitter.addWidget(self._tree_panel)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 1000])

        self._main_tabs.addTab(imervue_page, "Imervue")

        self._build_workspace_tabs()

        self._build_status_bar()

        self._init_services()

        self._restore_startup_geometry()

        # ===== Debug =====
        # Debug 模式下自動關閉
        # Auto close in debug mode
        if debug:
            self.debug_timer = QTimer()
            self.debug_timer.setInterval(10000)
            self.debug_timer.timeout.connect(self.debug_close)
            self.debug_timer.start()

    def _init_language_and_icon(self) -> None:
        """Language, per-folder state stores and the window / application icon."""
        # 語言支援
        # Language support
        self.language_wrapper = language_wrapper
        self.language_wrapper.reset_language(user_setting_dict.get("language", "English"))
        # Qt 自己的字串（確定 / 取消、檔案對話框…）也跟著語言走
        from Imervue.system.qt_translations import install_qt_translations
        install_qt_translations(QApplication.instance(), self.language_wrapper.language)
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


    def _init_services(self) -> None:
        """Toasts, clipboard monitor, menus, What's New, tab shortcuts, folder / screen watching."""
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
        # 模仿瀏覽器行為，註冊在 main window 範圍內。資料夾分頁列只在 Imervue
        # 分頁，其他分頁（Paint 的 Ctrl+T 變形、Ctrl+W 關閉畫布分頁）有自己的
        # 同鍵動作；同一視窗兩個同鍵快捷鍵 Qt 視為歧義、兩個都不觸發，所以
        # 離開 Imervue 分頁時停用（_on_main_tab_changed）。
        self._folder_tab_shortcuts = [
            QShortcut(QKeySequence("Ctrl+T"), self, activated=self._new_tab),
            QShortcut(QKeySequence("Ctrl+W"), self, activated=self._close_current_tab),
            QShortcut(QKeySequence("Ctrl+Tab"), self, activated=self._next_tab),
            QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, activated=self._prev_tab),
        ]
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

    def _restore_startup_geometry(self) -> None:
        """Restore the window geometry and hook screen changes once the window exists."""
        # ===== 還原視窗位置與大小（多螢幕適配） =====
        self._restore_window_geometry()
        # Restoring geometry can jump the window from the primary screen it was
        # born on to a different monitor. Listen for that (and later drags) so
        # the view is re-fitted to the actual screen instead of keeping the
        # first screen's size. Deferred so windowHandle() exists.
        QTimer.singleShot(0, self._connect_screen_change_signal)

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
        for shortcut in self._folder_tab_shortcuts:
            shortcut.setEnabled(idx == 0)
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
        """Enable per-action tooltips on every menu of the window.

        Safe to call repeatedly — Qt's ``setToolTipsVisible`` is idempotent.
        The menus are found with ``findChildren``: walking them through
        ``QAction.menu()`` invalidated the cached ``language_menu`` wrapper
        (Imervue/gui/menu_tree.py), which is how plugin languages vanished
        from the Language menu.
        """
        for menu in self.findChildren(QMenu):
            try:
                menu.setToolTipsVisible(True)
            except RuntimeError:
                continue

    # ==========================
    # 狀態列
    # ==========================

    # ---------- Status bar info slots ----------

    # ==========================
    # 檢視模式 (Grid / List)
    # ==========================

    # ==========================
    # 雙圖顯示 (Split / Manga)
    # ==========================

    # ==========================
    # 多螢幕視窗
    # ==========================

    # ==========================
    # 劇場模式 (Theater mode)
    # ==========================

    # ==========================
    # 資料夾監控
    # ==========================

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
        with best_effort("show onboarding or What's New at startup", _logger):
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

    # ===== Drag-and-drop on the main window =====

    @classmethod
    def _is_supported_drop(cls, path: str) -> bool:
        """Return True iff the dropped path is a folder or an image with
        a recognised extension."""
        p = Path(path)
        if p.is_dir():
            return True
        return p.suffix.lower() in VIEWER_EXTENSIONS

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
            except Exception:   # load surface raises a wide variety
                logger = logging.getLogger("Imervue")
                logger.exception("drop-load failed: %s", target)
                if hasattr(self, "toast"):
                    lang = language_wrapper.language_word_dict
                    self.toast.error(
                        lang.get("drop_load_failed", "Couldn't open {name}").format(
                            name=target.name,
                        ),
                    )

    # ==========================
    # 拖到別的螢幕 → 自動適配
    # ==========================

    # ==========================
    # 多螢幕視窗位置記憶
    # ==========================

    def closeEvent(self, event):
        import logging
        logging.getLogger("Imervue").info("closeEvent triggered")

        self._release_for_close()
        self._persist_for_close()

        # Only the LAST main window runs the app-global teardown below. A
        # secondary window (File → New Window) shares this closeEvent; running
        # the plugin unload + os._exit for it would kill the whole process and
        # unload plugins out from under the windows that are still open.
        ImervueMainWindow._live_windows.discard(self)
        if _other_live_windows_remain(ImervueMainWindow._live_windows, self):
            event.accept()
            super().closeEvent(event)
            self.deleteLater()
            return

        # Plugin hook: app closing
        if hasattr(self, "plugin_manager"):
            with best_effort("notify plugins the app is closing and unload them", _logger):
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

    def _release_for_close(self) -> None:
        """Snapshot the folder session, then stop signals, watchers, workers and GL state.

        Each group is best-effort: a failure skips the rest of its group only.
        """
        # Snapshot the current folder's view state (incl. whether we're in deep
        # zoom) BEFORE any teardown clears the viewer, so relaunching can return
        # to where the user left off instead of always to the tile wall.
        with best_effort("save the folder session", _logger):
            self._save_current_folder_session()

        # --- 斷開分頁切換信號，避免銷毀過程中觸發 ---
        with best_effort("disconnect the tab-change signal", _logger):
            self._main_tabs.currentChanged.disconnect(self._on_main_tab_changed)

        # --- 停止 watchdog 觀察執行緒 ---
        with best_effort("stop the file-tree watchdog", _logger):
            if hasattr(self, "_tree_watchdog"):
                self._tree_watchdog.stop()

        # --- 等待背景刪除 worker，避免其 QThread 在 view 銷毀時仍在執行 ---
        # (次要視窗走 deleteLater → destroyed-while-running 崩潰；
        #  主視窗走 os._exit → 半途中止 OS 垃圾桶批次)
        with best_effort("stop the file-tree workers", _logger):
            self.tree.shutdown()

        # --- 安全關閉修改面板 ---
        # 停止預覽防抖計時器 — 未儲存的 recipe 變更在關閉時丟棄
        with best_effort("stop the Modify panel's preview debounce", _logger):
            self.modify_panel._debounce.stop()
            self.modify_panel.recipe_committed.disconnect()
        with best_effort("destroy the Modify canvas", _logger):
            self.modify_panel._destroy_canvas()
        with best_effort("clear the Modify undo stack", _logger):
            self.modify_panel._undo_stack.clear()

        # --- 安全關閉 OpenGL viewer ---
        with best_effort("free the viewer's GL textures", _logger):
            self.viewer.makeCurrent()
            self.viewer._delete_all_tile_textures()
            self.viewer._clear_deep_zoom()
            self.viewer.doneCurrent()

    def _persist_for_close(self) -> None:
        """Save window geometry and settings, then commit pending deletions (best-effort)."""
        # 儲存視窗位置與大小（在寫入設定之前）
        with best_effort("save the window geometry", _logger):
            self._save_window_geometry()

        # 最優先：儲存使用者設定（在任何可能失敗的操作之前）
        # 先取消任何待處理的 debounced save，避免背景 timer 在關閉過程中
        # 與我們的 flush 競爭寫同一個檔案
        with best_effort("cancel the pending settings save", _logger):
            cancel_pending_save()
        with best_effort("write the user settings", _logger):
            write_user_setting()

        with best_effort("commit pending deletions", _logger):
            commit_pending_deletions(self.viewer)

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
