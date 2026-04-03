import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QFileSystemModel, QSplitter, QSizePolicy
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import load_image, open_path
from Imervue.integration_guide import _init_plugin_system_example
from Imervue.menu.file_menu import build_file_menu
from Imervue.menu.language_menu import build_language_menu
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

        self.icon_path = Path.cwd() / "Imervue.ico"
        self.icon = QIcon(str(self.icon_path))
        self.setWindowIcon(self.icon)

        # ===== 中央 Splitter =====
        splitter = QSplitter()
        self.setCentralWidget(splitter)

        # ===== 左側檔案樹 =====
        self.model = QFileSystemModel()
        self.model.setRootPath("")

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(""))
        self.model.setNameFilters(["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff"])
        self.model.setNameFilterDisables(False)
        self.tree.clicked.connect(self.on_file_clicked)
        self.tree.resizeColumnToContents(0)
        self.tree.setColumnWidth(0, 400)
        self.tree.header().setStretchLastSection(True)

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

        # GPU Viewer 佔滿剩餘空間
        from Imervue.gpu_image_view.gpu_image_view import GPUImageView
        self.viewer = GPUImageView(main_window=self)
        right_layout.addWidget(self.viewer, stretch=1)

        self.viewer.on_filename_changed = lambda name: self.filename_label.setText(
            language_wrapper.language_word_dict.get("main_window_current_filename_format").format(name=name))

        splitter.addWidget(self.tree)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 1000])

        # ===== 選單列 =====
        self.create_menu()

        _init_plugin_system_example(self)

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
        build_language_menu(self)
        # Plugin menu is built after plugin system init (in integration_guide.py)
        build_tip_menu(self)

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
                load_image(self.viewer.model.images[0], self.viewer)

    # ==========================
    # 點擊檔案
    # ==========================
    def on_file_clicked(self, index):
        path = self.model.filePath(index)

        self.viewer.clear_tile_grid()
        open_path(main_gui=self.viewer, path=path)

        if Path(path).is_dir():
            self.filename_label.setText(
                language_wrapper.language_word_dict.get(
                    "main_window_current_folder_format"
                ).format(path=path)
            )

    def _open_startup_folder(self, folder: str):
        self.tree.setRootIndex(self.model.index(folder))
        open_path(main_gui=self.viewer, path=folder)

    def closeEvent(self, event):
        commit_pending_deletions(self.viewer)

        # Plugin hook: app closing
        if hasattr(self, "plugin_manager"):
            self.plugin_manager.dispatch_app_closing(self)
            self.plugin_manager.unload_all()

        event.accept()
        write_user_setting()
        super().closeEvent(event)

    @classmethod
    def debug_close(cls) -> None:
        """Debug 模式下強制退出 / Force exit in debug mode"""
        sys.exit(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImervueMainWindow()
    window.showMaximized()
    sys.exit(app.exec())
