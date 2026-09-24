"""Plugins that belong in an Extra Tools submenu must actually get a menu entry.

The menu hook receives the shared Plugins ``QMenu``. Eight plugins searched
that menu for the top-level "Extra Tools" menu, never found it and so added no
entry at all. They now look the submenu up by the object name the host gives
it (``extra_tools_menu.submenu_object_name``) and fall back to the Plugins
menu on a host that predates those names.
"""
from __future__ import annotations

import importlib

import pytest
from PySide6.QtWidgets import QMainWindow, QMenu

from Imervue.menu import extra_tools_menu

PLUGINS = [
    ("npr_filters.npr_filters_plugin", "NPRFiltersPlugin", "retouch_submenu"),
    ("ai_colorize.ai_colorize_plugin", "AIColorizePlugin", "develop_submenu"),
    ("ai_denoise.ai_denoise_plugin", "AIDenoisePlugin", "retouch_submenu"),
    ("ai_motion_deblur.ai_motion_deblur_plugin", "AIMotionDeblurPlugin", "retouch_submenu"),
    ("ai_portrait_relight.ai_portrait_relight_plugin", "AIPortraitRelightPlugin",
     "retouch_submenu"),
    ("ai_smart_resize.ai_smart_resize_plugin", "AISmartResizePlugin", "retouch_submenu"),
    ("ai_style_transfer.ai_style_transfer_plugin", "AIStyleTransferPlugin", "develop_submenu"),
    ("portrait_mode.portrait_mode", "PortraitModePlugin", "retouch_submenu"),
]


def _window(with_extra_tools: bool) -> tuple[QMainWindow, QMenu]:
    window = QMainWindow()
    window.viewer = None  # ImervuePlugin.__init__ reads it; the hooks under test do not
    if with_extra_tools:
        extra_tools_menu.build_extra_tools_menu(window)
    return window, window.menuBar().addMenu("Plugins")


def _plugin_class(module_name: str, class_name: str) -> type:
    return getattr(importlib.import_module(module_name), class_name)


@pytest.fixture
def opened(monkeypatch):
    """Record which plugin's dialog slot an entry triggers."""
    calls: list[type] = []

    def patch(cls: type) -> None:
        monkeypatch.setattr(cls, "_open_dialog", lambda self: calls.append(type(self)))

    return calls, patch


@pytest.mark.parametrize(("module_name", "class_name", "key"), PLUGINS)
def test_entry_lands_in_named_extra_tools_submenu(qapp, opened, module_name, class_name, key):
    calls, patch = opened
    cls = _plugin_class(module_name, class_name)
    patch(cls)
    window, plugin_menu = _window(with_extra_tools=True)
    try:
        submenu = window.findChild(QMenu, extra_tools_menu.submenu_object_name(key))
        before = list(submenu.actions())
        plugin = cls(window)  # the manager keeps plugins alive; Qt only holds a weak slot
        plugin.on_build_menu_bar(plugin_menu)
        added = [a for a in submenu.actions() if a not in before]
        assert len(added) == 1
        assert plugin_menu.actions() == []
        added[0].trigger()
        assert calls == [cls]
    finally:
        window.deleteLater()


@pytest.mark.parametrize(("module_name", "class_name", "key"), PLUGINS)
def test_entry_falls_back_to_plugins_menu_on_older_host(
    qapp, opened, module_name, class_name, key,
):
    del key
    calls, patch = opened
    cls = _plugin_class(module_name, class_name)
    patch(cls)
    window, plugin_menu = _window(with_extra_tools=False)
    try:
        plugin = cls(window)
        plugin.on_build_menu_bar(plugin_menu)
        assert len(plugin_menu.actions()) == 1
        plugin_menu.actions()[0].trigger()
        assert calls == [cls]
    finally:
        window.deleteLater()


def test_safety_review_reuses_the_ai_tools_submenu_without_invalidating_it(qapp):
    """safety_review joins the "AI Tools" submenu another plugin created.

    It used to find that submenu with ``QAction.menu()``, which invalidated
    the other plugin's cached wrapper of it.
    """
    import gc

    import shiboken6

    from Imervue.multi_language.language_wrapper import language_wrapper

    cls = _plugin_class("safety_review.safety_review", "SafetyReviewPlugin")
    window, plugin_menu = _window(with_extra_tools=False)
    try:
        title = language_wrapper.language_word_dict.get("bg_remove_menu", "AI Tools")
        ai_tools = plugin_menu.addMenu(title)   # as ai_background_remover does
        ai_tools.addAction("AI Background Removal")
        plugin = cls(window)
        plugin.on_build_menu_bar(plugin_menu)
        gc.collect()
        assert shiboken6.isValid(ai_tools)
        assert len(plugin_menu.actions()) == 1            # no second AI Tools submenu
        assert len(ai_tools.actions()) > 2                # safety review entries joined it
    finally:
        window.deleteLater()
