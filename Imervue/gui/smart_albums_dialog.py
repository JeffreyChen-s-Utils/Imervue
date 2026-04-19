"""
Smart Albums dialog — save / apply / delete rule-based dynamic albums.

Collects filter conditions from the UI (extensions, min dimensions,
color labels, rating, favorites, cull state, tag, name contains) and
persists them as JSON rules via ``library.smart_album``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QSpinBox, QCheckBox, QComboBox, QMessageBox,
)

from Imervue.library import smart_album
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow


_COLORS = ("red", "yellow", "green", "blue", "purple")
_CULL_VALUES = ("", "pick", "reject", "unflagged")


class SmartAlbumsDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("smart_albums_title", "Smart Albums"))
        self.resize(560, 520)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(lang.get("smart_albums_saved", "Saved albums")))
        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_album_clicked)
        layout.addWidget(self._list)

        row = QHBoxLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(lang.get("smart_albums_name", "Name"))
        row.addWidget(self._name_edit)
        save_btn = QPushButton(lang.get("smart_albums_save", "Save"))
        save_btn.clicked.connect(self._save)
        apply_btn = QPushButton(lang.get("smart_albums_apply", "Apply"))
        apply_btn.clicked.connect(self._apply)
        del_btn = QPushButton(lang.get("smart_albums_delete", "Delete"))
        del_btn.clicked.connect(self._delete)
        for b in (save_btn, apply_btn, del_btn):
            row.addWidget(b)
        layout.addLayout(row)

        layout.addWidget(QLabel(lang.get("smart_albums_rules", "Rules")))
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText(
            lang.get("smart_albums_exts", "extensions comma-sep (jpg,png)")
        )
        layout.addWidget(self._ext_edit)

        self._name_contains_edit = QLineEdit()
        self._name_contains_edit.setPlaceholderText(
            lang.get("smart_albums_name_contains", "name contains…")
        )
        layout.addWidget(self._name_contains_edit)

        row2 = QHBoxLayout()
        self._min_w = QSpinBox()
        self._min_w.setRange(0, 20000)
        self._min_w.setPrefix(lang.get("smart_albums_min_w_prefix", "min w "))
        self._min_h = QSpinBox()
        self._min_h.setRange(0, 20000)
        self._min_h.setPrefix(lang.get("smart_albums_min_h_prefix", "min h "))
        self._min_rating = QSpinBox()
        self._min_rating.setRange(0, 5)
        self._min_rating.setPrefix(lang.get("smart_albums_min_rating_prefix", "min★ "))
        row2.addWidget(self._min_w)
        row2.addWidget(self._min_h)
        row2.addWidget(self._min_rating)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self._color_combo = QComboBox()
        self._color_combo.addItem(lang.get("smart_albums_any_color", "-- any color --"), "")
        for c in _COLORS:
            self._color_combo.addItem(lang.get(f"color_label_{c}", c.title()), c)
        self._cull_combo = QComboBox()
        for v in _CULL_VALUES:
            self._cull_combo.addItem(
                v or lang.get("smart_albums_any_cull", "-- any cull --"), v,
            )
        self._fav_check = QCheckBox(lang.get("smart_albums_favorites", "Favorites only"))
        row3.addWidget(self._color_combo)
        row3.addWidget(self._cull_combo)
        row3.addWidget(self._fav_check)
        layout.addLayout(row3)

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText(
            lang.get("smart_albums_tags", "tags comma-sep (ALL must match)")
        )
        layout.addWidget(self._tags_edit)

        close_btn = QPushButton(lang.get("common_close", "Close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self._refresh_list()

    # ---------- Helpers ----------

    def _refresh_list(self) -> None:
        self._list.clear()
        for a in smart_album.list_all():
            self._list.addItem(a["name"])

    def _current_rules(self) -> dict:
        rules: dict = {}
        exts = [s.strip().lstrip(".") for s in self._ext_edit.text().split(",") if s.strip()]
        if exts:
            rules["exts"] = exts
        if self._name_contains_edit.text().strip():
            rules["name_contains"] = self._name_contains_edit.text().strip()
        if self._min_w.value():
            rules["min_width"] = self._min_w.value()
        if self._min_h.value():
            rules["min_height"] = self._min_h.value()
        if self._min_rating.value():
            rules["min_rating"] = self._min_rating.value()
        color = self._color_combo.currentData() or ""
        if color:
            rules["color_labels"] = [color]
        cull = self._cull_combo.currentData() or ""
        if cull:
            rules["cull"] = cull
        if self._fav_check.isChecked():
            rules["favorites_only"] = True
        tags = [s.strip() for s in self._tags_edit.text().split(",") if s.strip()]
        if tags:
            rules["tags_all"] = tags
        return rules

    def _load_rules(self, rules: dict) -> None:
        self._ext_edit.setText(",".join(rules.get("exts", [])))
        self._name_contains_edit.setText(rules.get("name_contains", ""))
        self._min_w.setValue(int(rules.get("min_width", 0) or 0))
        self._min_h.setValue(int(rules.get("min_height", 0) or 0))
        self._min_rating.setValue(int(rules.get("min_rating", 0) or 0))
        colors = rules.get("color_labels") or []
        idx = 0
        if colors:
            first = colors[0]
            for i in range(self._color_combo.count()):
                if self._color_combo.itemData(i) == first:
                    idx = i
                    break
        self._color_combo.setCurrentIndex(idx)
        cull = rules.get("cull") or ""
        cull_idx = 0
        for i in range(self._cull_combo.count()):
            if self._cull_combo.itemData(i) == cull:
                cull_idx = i
                break
        self._cull_combo.setCurrentIndex(cull_idx)
        self._fav_check.setChecked(bool(rules.get("favorites_only", False)))
        self._tags_edit.setText(",".join(rules.get("tags_all") or []))

    # ---------- Actions ----------

    def _on_album_clicked(self, item) -> None:
        data = smart_album.get(item.text())
        if data is None:
            return
        self._name_edit.setText(data["name"])
        self._load_rules(data["rules"])

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "", "Name required")
            return
        smart_album.save(name, self._current_rules())
        self._refresh_list()
        if hasattr(self._ui, "toast"):
            self._ui.toast.success(
                language_wrapper.language_word_dict.get(
                    "smart_albums_saved_toast", "Saved: {name}"
                ).format(name=name)
            )

    def _delete(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            return
        if smart_album.delete(name):
            self._refresh_list()
            self._name_edit.clear()

    def _apply(self) -> None:
        rules = self._current_rules()
        viewer = self._ui.viewer
        base = getattr(viewer, "_unfiltered_images", None) or list(viewer.model.images)
        filtered = smart_album.apply_to_paths(base, rules)
        if not filtered:
            if hasattr(self._ui, "toast"):
                self._ui.toast.info(
                    language_wrapper.language_word_dict.get(
                        "smart_albums_no_match", "No images match"
                    )
                )
            return
        viewer._unfiltered_images = list(base)
        viewer.clear_tile_grid()
        viewer.load_tile_grid_async(filtered)
        self.accept()


def open_smart_albums(ui: ImervueMainWindow) -> None:
    SmartAlbumsDialog(ui).exec()
