"""Cancellable filename search with separate preview and tree-location actions."""
import os
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Signal, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget, QToolButton, QSizePolicy,
)

from Imervue.gui.file_tree_search_scan import scan_matches
from Imervue.multi_language.language_wrapper import language_wrapper

_MISSING_RESULT = "This result no longer exists"

_running_scans: set = set()


class _Scan(QThread):
    batch = Signal(int, object)
    complete = Signal(int, bool, int)

    def __init__(self, generation: int, root: str, query: str, excluded: frozenset[str]):
        super().__init__()
        self.generation = generation
        self.root = root
        self.query = query
        self.excluded = excluded
        self.cancelled = Event()

    def run(self) -> None:
        unreadable = scan_matches(self.root, self.query, self.cancelled,
                                  lambda batch: self.batch.emit(self.generation, batch),
                                  excluded=self.excluded)
        self.complete.emit(self.generation, self.cancelled.is_set(), unreadable)


class FileTreeSearch(QObject):
    path_activated = Signal(str)

    def __init__(self, tree):
        super().__init__(tree)
        self.tree = tree
        self.query = ""
        self.generation = 0
        self.worker = None
        self._locate_path = ""
        self._locate_loading = set()
        self.panel = QWidget()
        self.panel.setObjectName("treeSearchPanel")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self.start)
        self._locate_timer = QTimer(self)
        self._locate_timer.setSingleShot(True)
        self._locate_timer.timeout.connect(self._finish_locate)
        self._build_panel()
        loaded = getattr(tree.model(), "directoryLoaded", None)
        if loaded is not None:
            loaded.connect(self._directory_loaded)
        self._cancel_events = set()
        tree.destroyed.connect(lambda: [event.set() for event in self._cancel_events])

    def _build_panel(self) -> None:
        lang = language_wrapper.language_word_dict
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scope = QLabel()
        self.scope.setObjectName("treeSearchScope")
        self.scope.setTextFormat(Qt.TextFormat.PlainText)
        self.scope.setWordWrap(True)
        self.scope.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.scope.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.scope)
        row = QHBoxLayout()
        self.include = QCheckBox(lang.get("tree_search_recursive", "Include subfolders"))
        self.include.setObjectName("treeSearchRecursive")
        self.include.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.include.setToolTip(self.include.text())
        self.include.toggled.connect(self._mode_changed)
        self.cancel_button = QToolButton()
        self.cancel_button.setText("×")
        self.cancel_button.setToolTip(lang.get("tree_search_cancel", "Cancel"))
        self.cancel_button.setAccessibleName(self.cancel_button.toolTip())
        self.cancel_button.setObjectName("treeSearchCancel")
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setVisible(False)
        row.addWidget(self.include, 1)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("treeSearchCollapse")
        self.collapse_button.setCheckable(True)
        self.collapse_button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.collapse_button.setChecked(True)
        self.collapse_button.setText(lang.get("tree_search_results", "Search results"))
        self.collapse_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.collapse_button.toggled.connect(self._update_visibility)
        self.collapse_button.setVisible(False)
        layout.addWidget(self.collapse_button)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setVisible(False)
        layout.addWidget(self.status)
        self.results = QListWidget()
        self.results.setObjectName("treeSearchResults")
        self.results.setMaximumHeight(220)
        self.results.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.results.setVisible(False)
        self.results.itemActivated.connect(self._activate)
        layout.addWidget(self.results)
        self.locate_button = QPushButton(lang.get("tree_search_locate", "Locate in tree"))
        self.locate_button.setObjectName("treeSearchLocate")
        self.locate_button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.locate_button.setVisible(False)
        self.locate_button.clicked.connect(self._locate_selected)
        layout.addWidget(self.locate_button)
        self._update_scope()

    @property
    def recursive(self) -> bool:
        return self.include.isChecked()

    def _mode_changed(self, _checked: bool) -> None:
        self.tree.set_search_text(self.query)
        self._update_visibility()
        self._update_scope()

    def _update_visibility(self) -> None:
        self.status.setVisible(self.recursive)
        self.collapse_button.setVisible(self.recursive)
        expanded = self.collapse_button.isChecked()
        self.collapse_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.results.setVisible(self.recursive and expanded)
        self.locate_button.setVisible(self.recursive and expanded)

    def _update_scope(self) -> None:
        lang = language_wrapper.language_word_dict
        root = self.tree._tree_state.root
        label = lang.get("tree_search_scope", "Search folder: {folder}")
        self.scope.setText(label.format(folder=Path(root).name or root) if root else
                           lang.get("tree_search_choose_root", "Open a folder to search"))
        self.scope.setToolTip(root)

    def set_query(self, text: str) -> None:
        self.query = text.strip()
        self._locate_path = ""
        self._locate_timer.stop()
        self.cancel()
        self.results.clear()
        self.status.clear()
        if self.recursive and self.query:
            self._timer.start()

    def root_changed(self) -> None:
        self._locate_path = ""
        self._locate_timer.stop()
        self.set_query(self.query)
        self._update_scope()

    def cancel(self) -> None:
        self._timer.stop()
        self.generation += 1
        if self.worker is not None:
            self.worker.cancelled.set()
            self.worker = None
            lang = language_wrapper.language_word_dict
            self.status.setText(lang.get("tree_search_cancelled", "Search cancelled"))
        self.cancel_button.setVisible(False)

    def start(self) -> None:
        self.cancel()
        root = self.tree._tree_state.root
        lang = language_wrapper.language_word_dict
        if not self.recursive or not self.query:
            return
        if not root or not Path(root).is_dir():
            self.status.setText(lang.get("tree_search_choose_root", "Open a folder to search"))
            return
        self.results.clear()
        self.status.setText(lang.get("tree_search_running", "Searching…"))
        self.cancel_button.setVisible(True)
        excluded = frozenset(os.path.normcase(p) for p in self.tree._hidden_paths)
        worker = _Scan(self.generation, root, self.query, excluded)
        self.worker = worker
        _running_scans.add(worker)
        self._cancel_events.add(worker.cancelled)
        worker.batch.connect(self._accept_batch)
        worker.complete.connect(self._complete)
        worker.finished.connect(lambda w=worker: _running_scans.discard(w))
        events = self._cancel_events
        worker.finished.connect(lambda event=worker.cancelled: events.discard(event))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _accept_batch(self, generation: int, paths: list[str]) -> None:
        if generation != self.generation:
            return
        root = Path(self.tree._tree_state.root)
        hidden = [Path(p) for p in self.tree._hidden_paths]
        for path in paths:
            if any(Path(path).is_relative_to(folder) for folder in hidden):
                continue
            relative = Path(path).relative_to(root)
            label = relative.name
            if relative.parent != Path("."):
                label += "\n" + str(relative.parent)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.results.addItem(item)

    def _complete(self, generation: int, cancelled: bool, unreadable: int) -> None:
        if generation != self.generation:
            return
        self.worker = None
        self.cancel_button.setVisible(False)
        lang = language_wrapper.language_word_dict
        key = "tree_search_cancelled" if cancelled else "tree_search_complete"
        self.status.setText(lang.get(key, "{count} results; {skipped} unreadable entries").format(
            count=self.results.count(), skipped=unreadable))

    def _activate(self, item) -> None:
        if item is not None:
            path = item.data(Qt.ItemDataRole.UserRole)
            if self._hidden(path) or not Path(path).exists():
                self.status.setText(language_wrapper.language_word_dict.get(
                    "tree_search_missing", _MISSING_RESULT))
                return
            self.path_activated.emit(path)

    def _locate_selected(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            self.locate(item.data(Qt.ItemDataRole.UserRole))

    def _hidden(self, path: str) -> bool:
        return any(Path(path).is_relative_to(Path(folder)) for folder in self.tree._hidden_paths)

    def exclude_hidden(self) -> None:
        for row in range(self.results.count() - 1, -1, -1):
            if self._hidden(self.results.item(row).data(Qt.ItemDataRole.UserRole)):
                self.results.takeItem(row)
        if self._locate_path and self._hidden(self._locate_path):
            self._locate_path = ""
            self._locate_timer.stop()

    def locate(self, path: str) -> None:
        if self._hidden(path) or not Path(path).exists():
            self.status.setText(language_wrapper.language_word_dict.get(
                "tree_search_missing", _MISSING_RESULT))
            return
        self._locate_path = path
        self._locate_loading.clear()
        self._locate_attempts = 0
        self._finish_locate()

    def _directory_loaded(self, _path: str) -> None:
        self._locate_loading.discard(os.path.normcase(_path))
        if self._locate_path:
            self._locate_timer.start(0)

    def _finish_locate(self) -> None:
        if not self._locate_path:
            return
        root = Path(self.tree._tree_state.root)
        path = Path(self._locate_path)
        if self._hidden(str(path)) or not path.exists():
            self._locate_path = ""
            self.status.setText(language_wrapper.language_word_dict.get(
                "tree_search_missing", _MISSING_RESULT))
            return
        if not path.is_relative_to(root):
            self._locate_path = ""
            return
        model = self.tree.model()
        self._expand_ancestors(path, root)
        index = model.index(str(path))
        self._locate_attempts += 1
        if index.isValid():
            self.tree.setCurrentIndex(index)
            self.tree.scrollTo(index)
        if self._locate_attempts < 3:
            self._locate_timer.start(30)
        elif (not self._locate_loading and index.isValid()
              and not self.tree.visualRect(index).isEmpty()):
            self._locate_path = ""

    def _expand_ancestors(self, path: Path, root: Path) -> None:
        model = self.tree.model()
        for parent in reversed(path.parents):
            if parent != root and parent.is_relative_to(root):
                index = model.index(str(parent))
                if index.isValid():
                    if model.canFetchMore(index):
                        self._locate_loading.add(os.path.normcase(str(parent)))
                        model.fetchMore(index)
                    self.tree.expand(index)

    def shutdown(self) -> None:
        self.cancel()
        self._locate_timer.stop()
