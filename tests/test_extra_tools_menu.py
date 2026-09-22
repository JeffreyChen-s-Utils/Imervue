"""The colour-blindness preview actions must pass their mode, not the checked bool.

Each CVD entry connected ``lambda _kind=kind: _set_cvd_mode(ui, _kind)`` to
``QAction.triggered``. triggered emits a ``checked`` bool, which PySide6 fed into
the lambda's single parameter -- so ``_kind`` became ``False`` and every mode but
"Off" was ignored as an unknown mode. The lambda now takes ``checked`` first.

The test captures the callbacks ``_build_cvd_submenu`` wires (by stubbing
``_add_action``) and invokes each the way Qt does -- passing the checked bool to
the multi-arg kind callbacks -- so no real QMenu/QAction is constructed.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.menu import extra_tools_menu


def _capture_cvd_callbacks(ui, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        extra_tools_menu, "_add_action",
        lambda menu, lang, key, fallback, cb: captured.__setitem__(key, cb),
    )
    parent = SimpleNamespace(addMenu=lambda _title: SimpleNamespace())
    extra_tools_menu._build_cvd_submenu(parent, ui, {})
    return captured


def test_cvd_kind_actions_pass_the_mode_not_the_checked_bool(monkeypatch):
    received: list = []
    ui = SimpleNamespace(viewer=SimpleNamespace(set_cvd_view_mode=received.append))
    callbacks = _capture_cvd_callbacks(ui, monkeypatch)

    for kind in ("protanopia", "deuteranopia", "tritanopia", "achromatopsia"):
        received.clear()
        callbacks[f"cvd_view_{kind}"](False)   # Qt delivers triggered(checked=False)
        assert received == [kind]              # not [False]


def test_cvd_off_action_clears_the_mode(monkeypatch):
    received: list = []
    ui = SimpleNamespace(viewer=SimpleNamespace(set_cvd_view_mode=received.append))
    callbacks = _capture_cvd_callbacks(ui, monkeypatch)
    callbacks["cvd_view_off"]()               # zero-arg callback, like Qt calls it
    assert received == [None]


# ---------------------------------------------------------------------------
# Stable object names (the lookup contract plugins rely on)
# ---------------------------------------------------------------------------

_SUBMENU_KEYS = (
    "batch_submenu", "library_submenu", "views_submenu", "workflow_submenu",
    "export_submenu", "develop_submenu", "retouch_submenu", "multi_image_submenu",
)


def test_submenu_object_name_is_prefixed_key():
    assert extra_tools_menu.submenu_object_name("retouch_submenu") == "extra_tools.retouch_submenu"


def test_add_submenu_titles_and_names_the_submenu():
    created: list = []

    class _Sub:
        def setObjectName(self, name):  # noqa: N802 - Qt API
            self.name = name

    def add_menu(title):
        sub = _Sub()
        sub.title = title
        created.append(sub)
        return sub

    sub = extra_tools_menu._add_submenu(
        SimpleNamespace(addMenu=add_menu), {"x_submenu": "Localised"}, "x_submenu", "Fallback",
    )
    assert created == [sub]
    assert (sub.title, sub.name) == ("Localised", "extra_tools.x_submenu")
    missing = extra_tools_menu._add_submenu(
        SimpleNamespace(addMenu=add_menu), {}, "y_submenu", "Fallback",
    )
    assert missing.title == "Fallback"


def test_built_menu_exposes_every_submenu_by_object_name(qapp):
    from PySide6.QtWidgets import QMainWindow, QMenu

    from Imervue.multi_language.language_wrapper import language_wrapper

    window = QMainWindow()
    try:
        extra_tools_menu.build_extra_tools_menu(window)
        lang = language_wrapper.language_word_dict
        top = window.findChild(QMenu, extra_tools_menu.EXTRA_TOOLS_OBJECT_NAME)
        assert top is not None
        assert top.title() == lang.get("extra_tools_menu", "Extra Tools")
        for key in _SUBMENU_KEYS:
            sub = window.findChild(QMenu, extra_tools_menu.submenu_object_name(key))
            assert sub is not None, key
            assert sub.parent() is top
            assert sub.actions(), key
    finally:
        window.deleteLater()
