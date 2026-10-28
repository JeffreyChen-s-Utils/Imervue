"""Save and restore file-tree positions by path across asynchronous model reloads."""
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QTimer, QItemSelectionModel
from PySide6.QtWidgets import QAbstractItemView

from Imervue.gui.file_tree_preferences import root_key
from Imervue.user_settings.user_setting_dict import user_setting_dict
from Imervue.user_settings import user_setting_dict as settings_store


@dataclass(frozen=True)
class TreeViewState:
    expanded: tuple[str, ...] = ()
    selected: tuple[str, ...] = ()
    current: str = ""
    top_visible: str = ""
    top_offset: int = 0
    horizontal_scroll: int = 0

    @classmethod
    def from_dict(cls, value):
        value = value if isinstance(value, dict) else {}
        paths = {}
        for key in ("expanded", "selected"):
            items = value.get(key, ())
            paths[key] = tuple(p for p in items if isinstance(p, str)) if isinstance(
                items, (list, tuple)) else ()
        strings = {key: value.get(key, "") if isinstance(value.get(key), str) else ""
                   for key in ("current", "top_visible")}
        numbers = {key: value.get(key, 0) if type(value.get(key)) is int else 0
                   for key in ("top_offset", "horizontal_scroll")}
        return cls(**paths, **strings, **numbers)


class FileTreeState(QObject):
    def __init__(self, tree):
        super().__init__(tree)
        self.tree = tree
        self.root = ""
        self.pending = None
        self._attempts = 0
        self._loading = set()
        self._loaded = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.restore)

    def bind_model(self, model) -> None:
        loaded = getattr(model, "directoryLoaded", None)
        if loaded is not None:
            loaded.connect(self._directory_loaded)

    def _directory_loaded(self, _path: str) -> None:
        self._loading.discard(root_key(_path))
        self._loaded.add(root_key(_path))
        if self.pending is not None:
            self._timer.start(0)

    def _expanded_paths(self, parent):
        model = self.tree.model()
        paths = []
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            if self.tree.isExpanded(index):
                paths.append(model.filePath(index))
                paths.extend(self._expanded_paths(index))
        return paths

    def save(self) -> None:
        if not self.root or self.pending is not None:
            return
        tree = self.tree
        model = tree.model()
        if model is None or not hasattr(model, "filePath"):
            return
        top = tree.indexAt(QPoint(1, 1))
        selection = tree.selectionModel()
        state = TreeViewState(
            tuple(self._expanded_paths(tree.rootIndex())),
            tuple(model.filePath(i) for i in selection.selectedRows()),
            model.filePath(tree.currentIndex()) if tree.currentIndex().isValid() else "",
            model.filePath(top) if top.isValid() else "",
            tree.visualRect(top).top() if top.isValid() else 0,
            tree.horizontalScrollBar().value(),
        )
        states = user_setting_dict.get("tree_view_states", {})
        user_setting_dict["tree_view_states"] = {
            **(states if isinstance(states, dict) else {}), root_key(self.root): asdict(state),
        }
        settings_store.schedule_save()

    def begin_refresh(self) -> None:
        self._loaded.discard(root_key(self.root))

    def set_root(self, path: str) -> None:
        self._timer.stop()
        self.root = path
        self._loading = {root_key(path)} if path and root_key(path) not in self._loaded else set()
        states = user_setting_dict.get("tree_view_states", {})
        value = states.get(root_key(path)) if isinstance(states, dict) and path else None
        self.pending = TreeViewState.from_dict(value) if isinstance(value, dict) else None
        self._attempts = 0
        if self.pending is not None:
            self._timer.start(0)

    def _inside_root(self, path: str) -> bool:
        try:
            return bool(path) and Path(path).is_relative_to(Path(self.root))
        except ValueError:
            return False

    def _index(self, path: str):
        if not self._inside_root(path) or not Path(path).exists():
            return None
        index = self.tree.model().index(path)
        return index if index.isValid() else None

    def restore(self) -> None:
        state = self.pending
        if state is None:
            return
        tree = self.tree
        model = tree.model()
        waiting = root_key(self.root) in self._loading
        for path in sorted(state.expanded, key=lambda p: len(Path(p).parts)):
            index = self._index(path)
            if index is not None:
                if model.canFetchMore(index):
                    self._loading.add(root_key(path))
                    model.fetchMore(index)
                tree.expand(index)
                waiting = waiting or root_key(path) in self._loading
        current = self._index(state.current)
        if current is not None:
            tree.setCurrentIndex(current)
        selection = tree.selectionModel()
        selection.clearSelection()
        for path in state.selected:
            index = self._index(path)
            if index is not None:
                selection.select(index, QItemSelectionModel.SelectionFlag.Select
                                 | QItemSelectionModel.SelectionFlag.Rows)
        top = self._index(state.top_visible)
        if top is not None:
            tree.scrollTo(top, QAbstractItemView.ScrollHint.PositionAtTop)
            tree.verticalScrollBar().setValue(tree.verticalScrollBar().value() - state.top_offset)
        tree.horizontalScrollBar().setValue(state.horizontal_scroll)
        self._attempts += 1
        if self._attempts < 3:
            self._timer.start(30)
        elif not waiting:
            self.pending = None
