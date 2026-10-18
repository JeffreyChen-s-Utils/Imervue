"""Localized help text and field names inferred from actual Qt labels and layouts."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QFormLayout, QGridLayout, QLabel, QWidget

from Imervue.multi_language.english import english_word_dict
from Imervue.multi_language.language_wrapper import language_wrapper

_description_source = None
_description_count = 0
_descriptions: dict[str, list[tuple[str, str]]] = {}
_SCOPES = {
    "list_col_rating": "imagefilterbar",
    "image_filter": "imagefilterbar",
    "desktop_pet": "petworkspace petwindow",
    "puppet": "puppetworkspace parameterdock motiondock expressiondock posedock bonetreedock",
    "paint": "paintworkspace paintcanvas",
    "annotation": "modifypropertytabs annotationdialog annotationcanvas",
    "develop": "modifypropertytabs developpanel",
}


def readable_text(text: str) -> str:
    """Keep literal label content, converting rich text to readable text only."""
    if re.search(r"<[a-zA-Z][^>]*>", text):
        document = QTextDocument()
        document.setHtml(text)
        text = document.toPlainText()
    return text


def plain_label(text: str, *, rich=True) -> str:
    """Remove rich text, mnemonic markers and display-only punctuation."""
    text = readable_text(text) if rich else text
    return re.sub(r"&(?!&)", "", text).replace("&&", "&").strip().rstrip(".。…:： ")


def word(key: str, **values) -> str:
    """Resolve a help string through the active language and built-in fallback."""
    template = language_wrapper.language_word_dict.get(key, english_word_dict[key])
    return template.format(**values)


def existing_description(label: str, owner=None) -> str:
    """Reuse authored help associated with a translated control label, when available."""
    global _description_source, _description_count, _descriptions
    lang = language_wrapper.language_word_dict
    if lang is not _description_source or len(lang) != _description_count:
        _description_source, _description_count = lang, len(lang)
        _descriptions = {}
        for key in english_word_dict.keys() | lang.keys():
            suffix = next((s for s in ("_tooltip", "_tip") if key.endswith(s)), "")
            if not suffix:
                continue
            value = lang.get(key[:-len(suffix)], english_word_dict.get(key[:-len(suffix)], ""))
            description = lang.get(key, english_word_dict.get(key, ""))
            if value and description and "{" not in description:
                _descriptions.setdefault(plain_label(value), []).append((key, description))
    candidates = _descriptions.get(label, [])
    context = []
    node = owner
    while node is not None:
        context.extend((type(node).__name__.lower(), node.objectName().lower()))
        node = node.parent()
    context = " ".join(context)
    scoped = []
    generic = []
    for key, description in candidates:
        scope = next((scope for prefix, scope in _SCOPES.items() if key.startswith(prefix)), "")
        if scope:
            if any(name in context for name in scope.split()):
                scoped.append(description)
        else:
            prefix = key.split("_")[0]
            if prefix in context:
                scoped.append(description)
            else:
                generic.append(description)
    if scoped:
        return scoped[0] if len(set(scoped)) == 1 else ""
    return generic[0] if len(set(generic)) == 1 else ""


def _contains(item, widget) -> bool:
    child = item.widget()
    if child is not None:
        return child is widget or child.isAncestorOf(widget)
    nested = item.layout()
    return nested is not None and any(_contains(nested.itemAt(i), widget)
                                      for i in range(nested.count()))


def _layout_label(layout, widget) -> str:
    if isinstance(layout, QFormLayout):
        label = layout.labelForField(widget)
        if isinstance(label, QLabel):
            return plain_label(label.text())
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if not _contains(item, widget):
            continue
        nested = item.layout()
        if nested is not None and (label := _layout_label(nested, widget)):
            return label
        for previous in range(index - 1, -1, -1):
            label = layout.itemAt(previous).widget()
            if isinstance(layout, QGridLayout):
                row, column, *_ = layout.getItemPosition(index)
                other_row, other_column, *_ = layout.getItemPosition(previous)
                if row != other_row or other_column >= column:
                    continue
            if isinstance(label, QLabel) and label.text().strip():
                return plain_label(label.text())
            if label is not None:
                break
    return ""


def control_label(widget: QWidget) -> str:
    """Prefer accessible names, buddies and adjacent form labels over container titles."""
    if widget.accessibleName():
        return plain_label(widget.accessibleName())
    parent = widget.parentWidget()
    for _ in range(4):
        if parent is None:
            break
        for label in parent.findChildren(QLabel, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if label.buddy() is widget:
                return plain_label(label.text())
        if parent.layout() is not None and (label := _layout_label(parent.layout(), widget)):
            return label
        if hasattr(parent, "title") and parent.title():
            return plain_label(parent.title())
        if parent.windowTitle():
            return plain_label(parent.windowTitle())
        parent = parent.parentWidget()
    return ""
