"""Sanity audit for every plugin shipped under ``plugins/``.

Each plugin must:
  * be importable via ``import <name>``,
  * expose a ``plugin_class`` attribute on the package,
  * subclass :class:`Imervue.plugin.plugin_base.ImervuePlugin`,
  * declare the four required class attributes,
  * return a dict-shaped ``get_translations()`` result.

These are the exact gates that ``plugin_manager.discover_and_load``
walks at runtime, so a regression in any of them would break the app
silently. Catching it in the test matrix is cheaper.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from Imervue.plugin.plugin_base import ImervuePlugin


def _plugin_dirs() -> list[Path]:
    root = Path(__file__).resolve().parent.parent / "plugins"
    if not root.is_dir():
        return []
    return sorted(
        d for d in root.iterdir()
        if d.is_dir() and (d / "__init__.py").exists()
    )


PLUGIN_NAMES = [d.name for d in _plugin_dirs()]


@pytest.mark.parametrize("plugin_name", PLUGIN_NAMES)
def test_plugin_imports(plugin_name):
    """Every plugin package imports without raising."""
    module = importlib.import_module(plugin_name)
    assert module is not None


@pytest.mark.parametrize("plugin_name", PLUGIN_NAMES)
def test_plugin_exposes_plugin_class(plugin_name):
    """Every plugin's ``__init__.py`` sets ``plugin_class``."""
    module = importlib.import_module(plugin_name)
    plugin_class = getattr(module, "plugin_class", None)
    assert plugin_class is not None, (
        f"{plugin_name}/__init__.py missing 'plugin_class' attribute"
    )


@pytest.mark.parametrize("plugin_name", PLUGIN_NAMES)
def test_plugin_class_extends_base(plugin_name):
    """``plugin_class`` is a real subclass of ``ImervuePlugin``."""
    module = importlib.import_module(plugin_name)
    plugin_class = module.plugin_class
    assert issubclass(plugin_class, ImervuePlugin), (
        f"{plugin_name}.plugin_class is not an ImervuePlugin subclass"
    )


@pytest.mark.parametrize("plugin_name", PLUGIN_NAMES)
def test_plugin_class_has_required_attributes(plugin_name):
    """Required class attributes have non-empty values."""
    module = importlib.import_module(plugin_name)
    plugin_class = module.plugin_class
    for attr in ("plugin_name", "plugin_version", "plugin_description", "plugin_author"):
        value = getattr(plugin_class, attr, None)
        assert value, f"{plugin_name}.plugin_class.{attr} is empty"


@pytest.mark.parametrize("plugin_name", PLUGIN_NAMES)
def test_plugin_translations_shape(plugin_name, qapp):
    """``get_translations()`` returns a ``dict[str, dict[str, str]]`` (or empty)."""
    module = importlib.import_module(plugin_name)

    # Plugin __init__ touches main_window.viewer; mock that minimally.
    from unittest.mock import MagicMock
    mw = MagicMock()
    mw.viewer = MagicMock()
    instance = module.plugin_class(mw)

    translations = instance.get_translations()
    assert isinstance(translations, dict), (
        f"{plugin_name}.get_translations() must return a dict, "
        f"got {type(translations).__name__}"
    )
    # Every value, if present, must itself be a dict[str, str]
    for lang, mapping in translations.items():
        assert isinstance(lang, str)
        assert isinstance(mapping, dict), (
            f"{plugin_name}.get_translations()[{lang!r}] must be a dict"
        )
        for key, value in mapping.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


def test_at_least_one_plugin_present():
    """The plugin directory should contain at least one valid plugin."""
    assert PLUGIN_NAMES, "No plugins discovered under plugins/"


def test_known_plugins_are_present():
    """Audit guard — fail loudly if a plugin we expected is missing.

    Updating this list is intentional: someone adding/removing a plugin
    should also update the list, signalling the intent in the diff.
    """
    expected = {
        "ai_background_remover",
        "ai_colorize",
        "ai_denoise",
        "ai_style_transfer",
        "object_splitter",
        "portrait_mode",
        "safety_review",
    }
    missing = expected - set(PLUGIN_NAMES)
    assert not missing, f"Expected plugins are missing: {sorted(missing)}"
