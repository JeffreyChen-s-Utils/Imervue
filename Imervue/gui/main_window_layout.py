"""Widget layout of the main window.

File tree, viewer column, image tab bar, view stack, workspace tabs and status bar.

``MainWindowLayoutMixin`` holds the ``_build_*`` methods ``ImervueMainWindow``'s
constructor calls to create its widgets; each stores the widgets it creates on
the window and returns the container it built.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QSizePolicy, QSplitter,
    QStackedWidget, QStatusBar, QTabBar, QVBoxLayout, QWidget,
)

from Imervue.gui.exif_sidebar import ExifSidebar
from Imervue.gui.file_tree_sort import FileTreeSortProxy
from Imervue.gui.file_tree_view import _FileTreeView
from Imervue.gui.folder_thumbnail_model import DEFAULT_ICON_SIZE, FolderThumbnailModel
from Imervue.image.formats import VIEWER_EXTENSIONS
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict


class MainWindowLayoutMixin:
    """The main window's widget builders, mixed into ``ImervueMainWindow``."""

    def _build_file_tree(self) -> None:
        """File tree of tab 0: filtered model, view, sort and search controls."""
        # ===== 左側檔案樹 =====
        # FolderThumbnailModel 供縮圖與檔案系統存取；FileTreeSortProxy 供
        # 具名排序鍵（含 QFileSystemModel 沒有欄位的「建立日期」），並轉發
        # QFileSystemModel 介面，所以其餘程式照舊把它當檔案系統 model 用。
        self.model = FileTreeSortProxy(FolderThumbnailModel())
        # 只篩選圖片格式 + 資料夾，隱藏不符合的檔案
        self.model.setNameFilters([f"*{ext}" for ext in sorted(VIEWER_EXTENSIONS)])
        self.model.setNameFilterDisables(False)

        # 設定起始路徑：有上次資料夾就用，否則從根開始
        last_folder = user_setting_dict.get("user_last_folder", "")
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

    def _build_viewer_column(self):
        """Viewer column of tab 0: image tabs, breadcrumb, filter row, viewer and view stack."""
        # ===== 右側 GPU Viewer + Label =====
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_widget.setLayout(right_layout)

        right_layout.addWidget(self._build_image_tab_bar())

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
        self.viewer = GPUImageView(main_window=self)

        self.exif_sidebar = ExifSidebar(self)

        right_layout.addWidget(self._build_view_stack(), stretch=1)

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
        return right_widget

    def _build_image_tab_bar(self) -> QTabBar:
        """Browser-style bar of the open deep-zoom images; returns it for the layout."""
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
        return self._tab_bar

    def _build_view_stack(self) -> QSplitter:
        """Grid / list / dual view stack beside the EXIF sidebar; returns the row splitter."""
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
        return viewer_row


    def _build_workspace_tabs(self) -> None:
        """Tabs 1-4: Modify panel, Paint, Puppet and Desktop Pet, plus the tab-bar key filter."""
        # Tab 1: 修改面板 — 左面板 | 圖片 | 右面板
        # --------------------------------------------------------
        from Imervue.gui.develop_panel import DevelopPanel
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
        # 右面板：顯影滑桿 + 重設。中間的 AnnotationCanvas 由 modify_panel 在綁定圖片時
        # 插進 splitter 第 1 格；主檢視器留在 Imervue 分頁，Modify 分頁不會用到它。
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

        self._main_tabs.currentChanged.connect(self._on_main_tab_changed)
        # On the Modify / Paint tabs, Left/Right should page images (like
        # DeepZoom) instead of the tab bar's default "switch tab". Filter the
        # tab bar's key events — it is the widget that holds focus after a tab
        # click and consumes the arrows.
        self._main_tabs.tabBar().installEventFilter(self)

    def _build_status_bar(self) -> None:
        """Status bar with its info slots and the VRAM pressure indicator."""
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
