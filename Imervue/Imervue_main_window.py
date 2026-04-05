import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QDir, QFileSystemWatcher
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QFileSystemModel, QSplitter, QSizePolicy,
    QStatusBar, QProgressBar, QHeaderView,
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from Imervue.system.app_paths import icon_path as _app_icon_path
from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import open_path
from Imervue.gui.exif_sidebar import ExifSidebar
from Imervue.gui.toast import ToastManager
from Imervue.integration_guide import _init_plugin_system_example
from Imervue.menu.file_menu import build_file_menu
from Imervue.menu.filter_menu import build_filter_menu
from Imervue.menu.language_menu import build_language_menu
from Imervue.menu.recent_menu import rebuild_recent_menu
from Imervue.menu.sort_menu import build_sort_menu
from Imervue.menu.tip_menu import build_tip_menu
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import write_user_setting, read_user_setting, user_setting_dict


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

        # ===== 中央 Splitter =====
        splitter = QSplitter()
        self.setCentralWidget(splitter)

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

        self.tree = QTreeView()
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

        self.filename_label = QLabel(language_wrapper.language_word_dict.get("main_window_current_filename"))
        self.filename_label.setMinimumHeight(16)  # 保證有高度
        self.filename_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.filename_label.setWordWrap(False)
        self.filename_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right_layout.addWidget(self.filename_label, stretch=0)

        # GPU Viewer + EXIF Sidebar 水平排列
        from Imervue.gpu_image_view.gpu_image_view import GPUImageView
        self.viewer = GPUImageView(main_window=self)

        self.exif_sidebar = ExifSidebar(self)

        viewer_row = QSplitter(Qt.Orientation.Horizontal)
        viewer_row.addWidget(self.viewer)
        viewer_row.addWidget(self.exif_sidebar)
        viewer_row.setStretchFactor(0, 1)
        viewer_row.setStretchFactor(1, 0)
        right_layout.addWidget(viewer_row, stretch=1)

        def _on_name_changed(name):
            self.filename_label.setText(
                language_wrapper.language_word_dict.get("main_window_current_filename_format").format(name=name))
            self.exif_sidebar.update_info()

        self.viewer.on_filename_changed = _on_name_changed

        splitter.addWidget(self.tree)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 1000])

        # ===== 狀態列 =====
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("")
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(180)
        self._progress_bar.setVisible(False)
        self._status_bar.addWidget(self._status_label, stretch=1)
        self._status_bar.addPermanentWidget(self._progress_bar)

        # ===== Toast 通知 =====
        self.toast = ToastManager(self.viewer)

        # ===== 選單列 =====
        self.create_menu()

        _init_plugin_system_example(self)

        # ===== 資料夾監控 =====
        self._folder_watcher = QFileSystemWatcher(self)
        self._folder_watcher.directoryChanged.connect(self._on_watched_folder_changed)
        self._folder_refresh_timer = QTimer(self)
        self._folder_refresh_timer.setSingleShot(True)
        self._folder_refresh_timer.setInterval(500)  # 去抖動 500ms
        self._folder_refresh_timer.timeout.connect(self._do_folder_refresh)

        # ===== Debug =====
        # Debug 模式下自動關閉
        # Auto close in debug mode
        if debug:
            self.debug_timer = QTimer()
            self.debug_timer.setInterval(10000)
            self.debug_timer.timeout.connect(self.debug_close)
            self.debug_timer.start()

    # ==========================
    # 選單
    # ==========================
    def create_menu(self):
        build_file_menu(self)
        build_sort_menu(self)
        build_filter_menu(self)
        build_language_menu(self)
        # Plugin menu is built after plugin system init (in integration_guide.py)
        build_tip_menu(self)

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
            self.watch_folder(path)
        elif Path(path).is_file():
            self.viewer.clear_tile_grid()
            open_path(main_gui=self.viewer, path=path)

        rebuild_recent_menu(self)

    def _on_directory_loaded(self, directory: str):
        """QFileSystemModel 目錄載入完成回調，確保樹狀圖正確顯示"""
        idx = self.model.index(directory)
        if idx.isValid():
            self.tree.update(idx)

    def _open_startup_folder(self, folder: str):
        self.model.setRootPath(folder)
        self.tree.setRootIndex(self.model.index(folder))
        open_path(main_gui=self.viewer, path=folder)
        self.filename_label.setText(
            language_wrapper.language_word_dict.get(
                "main_window_current_folder_format"
            ).format(path=folder)
        )
        self.watch_folder(folder)

    def closeEvent(self, event):
        # 最優先：儲存使用者設定（在任何可能失敗的操作之前）
        try:
            write_user_setting()
        except Exception:
            pass

        try:
            commit_pending_deletions(self.viewer)
        except Exception:
            pass

        # Plugin hook: app closing
        if hasattr(self, "plugin_manager"):
            try:
                self.plugin_manager.dispatch_app_closing(self)
                self.plugin_manager.unload_all()
            except Exception:
                pass

        event.accept()
        super().closeEvent(event)
        QApplication.instance().quit()

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
    window.showMaximized()
    sys.exit(app.exec())
