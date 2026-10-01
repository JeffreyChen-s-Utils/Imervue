"""Extra Tools > Library & Metadata > Metadata Template: stamp title, description and keywords.

A stationery pad: type the title, description and keywords once — with
``{filename}``, ``{name}``, ``{folder}``, ``{date}`` and ``{year}`` filled in
per photo — and apply them to the selection, either into empty fields only
(keywords are added) or over what is there. The values are Imervue's own
(``image_titles`` / ``image_descriptions`` / tags), which **XMP Sidecars** and
**Export Metadata** write out. The template is remembered. The merge is
:func:`Imervue.user_settings.metadata_template.apply_template`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from Imervue.gpu_image_view.actions.select import selection_or_all
from Imervue.gui.dialog_rows import confirm
from Imervue.library.capture_time import exif_capture_time
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.metadata_template import TOKENS, apply_template, photo_tokens
from Imervue.user_settings.tags import add_tag, get_tags_for_image, remove_tag
from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

SETTING_KEY = "metadata_template"
_FIELD_KEYS = {"title": "image_titles", "description": "image_descriptions"}


def split_keywords(text: str) -> list[str]:
    """Comma-separated *text* as a list of distinct, trimmed keywords."""
    seen: list[str] = []
    for word in (part.strip() for part in text.split(",")):
        if word and word not in seen:
            seen.append(word)
    return seen


def template_from_fields(title: str, description: str, keywords: str) -> dict[str, object]:
    """The template of the filled-in fields; an empty field is left out and changes nothing."""
    template: dict[str, object] = {}
    if title.strip():
        template["title"] = title.strip()
    if description.strip():
        template["description"] = description.strip()
    words = split_keywords(keywords)
    if words:
        template["keywords"] = words
    return template


def current_fields(path: str) -> dict[str, object]:
    """The photo's title, description and keywords as Imervue holds them."""
    fields: dict[str, object] = {
        name: str((user_setting_dict.get(key) or {}).get(path, ""))
        for name, key in _FIELD_KEYS.items()
    }
    fields["keywords"] = list(get_tags_for_image(path))
    return fields


def apply_to_photo(path: str, template: dict[str, object], *, fill_empty_only: bool) -> bool:
    """Apply *template* to one photo's fields; True when anything changed (caller saves)."""
    before = current_fields(path)
    after = apply_template(before, template, photo_tokens(path, exif_capture_time(path)),
                           fill_empty_only=fill_empty_only)
    if after == before:
        return False
    for name, key in _FIELD_KEYS.items():
        values = user_setting_dict.setdefault(key, {})
        if after[name]:
            values[path] = after[name]
        else:
            values.pop(path, None)
    for word in after["keywords"]:
        add_tag(word, path)
    for word in before["keywords"]:
        if word not in after["keywords"]:
            remove_tag(word, path)
    return True


def apply_to_photos(paths: list[str], template: dict[str, object], *,
                    fill_empty_only: bool) -> int:
    """Apply *template* to every photo and save once; returns how many changed."""
    changed = sum(apply_to_photo(path, template, fill_empty_only=fill_empty_only)
                  for path in paths)
    if changed:
        schedule_save()
    return changed


class MetadataTemplateDialog(QDialog):
    """Edit the remembered template and apply it to *paths*."""

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("metadata_template_title", "Metadata Template"))
        self.setMinimumWidth(480)
        self._paths = list(paths)
        saved = user_setting_dict.get(SETTING_KEY) or {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.get(
            "metadata_template_source", "{count} photo(s) will be stamped.",
        ).format(count=len(self._paths))))
        form = QFormLayout()
        self._title = QLineEdit(str(saved.get("title", "")))
        self._description = QLineEdit(str(saved.get("description", "")))
        self._keywords = QLineEdit(", ".join(saved.get("keywords", []) or []))
        self._keywords.setPlaceholderText(lang.get("metadata_template_keywords_hint",
                                                   "comma-separated"))
        form.addRow(lang.get("metadata_template_field_title", "Title:"), self._title)
        form.addRow(lang.get("metadata_template_field_description", "Description:"),
                    self._description)
        form.addRow(lang.get("metadata_template_field_keywords", "Keywords:"), self._keywords)
        layout.addLayout(form)
        tokens = QLabel(lang.get("metadata_template_tokens", "Tokens: {tokens}").format(
            tokens=" ".join(f"{{{token}}}" for token in TOKENS)))
        tokens.setStyleSheet("color: #888;")
        layout.addWidget(tokens)
        self._fill_empty = QCheckBox(lang.get(
            "metadata_template_fill_empty", "Only fill empty fields (keywords are added)"))
        self._fill_empty.setChecked(bool(saved.get("fill_empty_only", True)))
        self._fill_empty.setToolTip(lang.get(
            "metadata_template_fill_empty_tooltip",
            "Off: the template's title and description replace the photo's, and its keywords "
            "replace the photo's tags"))
        layout.addWidget(self._fill_empty)
        self._status = QLabel("")
        layout.addWidget(self._status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply
                                   | QDialogButtonBox.StandardButton.Close)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.setEnabled(bool(self._paths))
        apply_btn.clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def template(self) -> dict[str, object]:
        """The template the fields describe (empty fields left out)."""
        return template_from_fields(self._title.text(), self._description.text(),
                                    self._keywords.text())

    def apply(self) -> int:
        """Remember the template, confirm, stamp the photos and report; returns how many changed."""
        lang = language_wrapper.language_word_dict
        template = self.template()
        fill_empty_only = self._fill_empty.isChecked()
        user_setting_dict[SETTING_KEY] = {
            "title": self._title.text().strip(), "description": self._description.text().strip(),
            "keywords": split_keywords(self._keywords.text()), "fill_empty_only": fill_empty_only}
        if not template:
            self._status.setText(lang.get("metadata_template_empty", "Fill in at least one field."))
            return 0
        question = lang.get("metadata_template_confirm", "Stamp the template on {count} "
                            "photo(s)?").format(count=len(self._paths))
        if not confirm(self, self.windowTitle(), question):
            return 0
        changed = apply_to_photos(self._paths, template, fill_empty_only=fill_empty_only)
        self._status.setText(lang.get("metadata_template_done", "Changed {changed} of {count} "
                                      "photo(s).").format(changed=changed, count=len(self._paths)))
        return changed


def open_metadata_template(ui: ImervueMainWindow) -> None:
    """Open the dialog on the selection, or on every image the viewer lists."""
    MetadataTemplateDialog(selection_or_all(getattr(ui, "viewer", None)), ui).exec()
