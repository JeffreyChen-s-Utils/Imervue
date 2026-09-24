"""Qt's own strings (OK / Cancel, Yes / No, "Close Tab") follow the UI language."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QTranslator
from PySide6.QtWidgets import QDialogButtonBox

from Imervue.system import qt_translations
from Imervue.system.qt_translations import install_qt_translations, qt_locale_for


@pytest.fixture
def app(qapp):
    yield qapp
    install_qt_translations(qapp, "English")   # leave no translator for later tests


def _installed(app) -> list[QTranslator]:
    return app.findChildren(QTranslator, "imervue_qtbase")


@pytest.mark.parametrize(("language", "locale"), [
    ("Traditional_Chinese", "zh_TW"),
    ("Chinese", "zh_CN"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("English", None),
    ("Spanish", None),   # a plugin language Qt ships no catalogue for
    ("", None),
])
def test_qt_locale_for(language, locale):
    assert qt_locale_for(language) == locale


def test_traditional_chinese_translates_qt_buttons(app):
    assert install_qt_translations(app, "Traditional_Chinese") is True
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    try:
        assert [b.text() for b in box.buttons()] == ["確定", "取消"]
        assert QCoreApplication.translate("CloseButton", "Close Tab") == "關閉分頁"
    finally:
        box.deleteLater()


@pytest.mark.parametrize("language", ["Chinese", "Japanese", "Korean"])
def test_each_builtin_language_has_a_catalogue(app, language):
    assert install_qt_translations(app, language) is True
    assert QCoreApplication.translate("CloseButton", "Close Tab") != "Close Tab"


def test_switching_replaces_the_translator_and_english_removes_it(app):
    install_qt_translations(app, "Japanese")
    install_qt_translations(app, "Traditional_Chinese")
    assert len(_installed(app)) == 1
    assert QCoreApplication.translate("CloseButton", "Close Tab") == "關閉分頁"
    assert install_qt_translations(app, "English") is False
    QCoreApplication.sendPostedEvents(None, 0)   # run the deleteLater
    assert QCoreApplication.translate("CloseButton", "Close Tab") == "Close Tab"


def test_missing_catalogue_is_logged_and_leaves_english(app, monkeypatch, caplog):
    monkeypatch.setitem(qt_translations._QT_LOCALES, "Klingon", "tlh")   # noqa: SLF001
    with caplog.at_level("WARNING", logger="Imervue.qt_translations"):
        assert install_qt_translations(app, "Klingon") is False
    assert "qtbase_tlh" in caplog.text
    assert _installed(app) == []
    assert QCoreApplication.translate("CloseButton", "Close Tab") == "Close Tab"
