"""Load Qt's own translations (``qtbase``) for the active UI language.

Qt's built-in widgets draw their text from Qt's catalogue, not from Imervue's
dictionaries. Without a translator, that text stays English in every language:

- dialog-button-box OK / Cancel;
- message-box Yes / No;
- the file dialog;
- the tab bar's close-button tooltip;
- line-edit context menus;
- the key-sequence editor's "Press shortcut".

PySide6 ships the ``qtbase_<locale>.qm`` files, so this module only has to
pick the right one.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator

logger = logging.getLogger("Imervue.qt_translations")

# Imervue language code -> Qt catalogue locale. English needs no translator.
_QT_LOCALES: dict[str, str] = {
    "Traditional_Chinese": "zh_TW",
    "Chinese": "zh_CN",
    "Japanese": "ja",
    "Korean": "ko",
}
_TRANSLATOR_NAME = "imervue_qtbase"


def qt_locale_for(language: str) -> str | None:
    """Return the ``qtbase`` locale for an Imervue language code, or ``None``."""
    return _QT_LOCALES.get(language)


def install_qt_translations(app: QCoreApplication, language: str) -> bool:
    """Install Qt's translator for ``language`` on ``app``; return whether one is active.

    Replaces a translator an earlier call installed, and removes it for English
    or for a language Qt has no catalogue for (a plugin language).
    """
    for old in app.findChildren(QTranslator, _TRANSLATOR_NAME):
        app.removeTranslator(old)
        old.setParent(None)   # out of findChildren now, not only once deleteLater runs
        old.deleteLater()
    locale = qt_locale_for(language)
    if locale is None:
        return False
    translator = QTranslator()
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not translator.load(f"qtbase_{locale}", folder):
        logger.warning("Qt translations qtbase_%s not found in %s", locale, folder)
        return False
    translator.setParent(app)   # the app keeps it alive for as long as it is installed
    translator.setObjectName(_TRANSLATOR_NAME)
    app.installTranslator(translator)
    return True
