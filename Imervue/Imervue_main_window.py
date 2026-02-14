import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QActionGroup, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog,
    QTreeView, QFileSystemModel, QSplitter, QSizePolicy
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from Imervue.gpu_image_view.actions.delete import commit_pending_deletions
from Imervue.gpu_image_view.images.image_loader import load_image


class ImervueMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Imervue")

        # Windows 平台設定 AppUserModelID
        # Set AppUserModelID for Windows platform
        self.id = "Imervue"
        from ctypes import windll
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(self.id)

        self.icon_path = Path(os.getcwd()) / "Imervue.ico"
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

        self.filename_label = QLabel("目前檔名：")
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

        self.viewer.on_filename_changed = lambda name: self.filename_label.setText(f"目前檔名：{name}")

        splitter.addWidget(self.tree)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 1000])

        # ===== 選單列 =====
        self.create_menu()

        # ===== 變數 =====

    # ==========================
    # 選單
    # ==========================
    def create_menu(self):
        menubar = self.menuBar()

        # ===== 檔案 =====
        file_menu = menubar.addMenu("檔案")

        open_folder_action = file_menu.addAction("開啟資料夾")
        open_folder_action.triggered.connect(self.open_folder)

        exit_action = file_menu.addAction("離開")
        exit_action.triggered.connect(self.close)

        # ===== Tile Size 選單 =====
        view_menu = menubar.addMenu("Thumbnail tile Size")

        tile_group = QActionGroup(self)
        tile_group.setExclusive(True)

        thumbnail_size = [128, 256, 512, 1024]

        for size in thumbnail_size:
            action = view_menu.addAction(f"{size} x {size}")
            action.setCheckable(True)

            if size == self.viewer.thumbnail_size:
                action.setChecked(True)

            tile_group.addAction(action)

            action.triggered.connect(
                lambda checked, s=size: self.change_tile_size(s)
            )

    def change_tile_size(self, size):
        self.viewer.thumbnail_size = size

        # 如果目前有載入圖片，重新刷新
        if self.viewer.model.images:
            if len(self.viewer.model.images) > 1:
                self.viewer.clear_tile_grid()
                self.viewer.load_tile_grid_async(image_paths=self.viewer.model.images)
            else:
                load_image(self.viewer.model.images[0], self.viewer)

    # ==========================
    # 開啟資料夾
    # ==========================
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "選擇資料夾")

        if folder:
            self.tree.setRootIndex(self.model.index(folder))

    # ==========================
    # 點擊檔案
    # ==========================
    def on_file_clicked(self, index):
        path = self.model.filePath(index)

        # 切換資料夾前先清空
        self.viewer.clear_tile_grid()

        if os.path.isdir(path):
            images = [
                os.path.join(path, f)
                for f in os.listdir(path)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff"))
            ]
            if images:
                self.viewer.load_tile_grid_async(image_paths=images)
                self.filename_label.setText(f"目前資料夾：{path}")
        elif os.path.isfile(path):
            if path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):
                load_image(path, self.viewer)
                self.viewer.current_index = 0
                self.viewer.image_list = [path]
                self.filename_label.setText(f"目前檔名：{os.path.basename(path)}")

    def closeEvent(self, event):
        commit_pending_deletions(self.viewer)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImervueMainWindow()
    window.showMaximized()
    sys.exit(app.exec())
