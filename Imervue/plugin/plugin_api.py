"""Plugin API versions: what a plugin may rely on from this Imervue, and the check refusing more.

Plugins reach users through the plugin downloader, independently of Imervue
releases, so a plugin can need main-program code an older install lacks. Such a
plugin names the plugin API version it needs in a ``plugin.json`` file beside its
``__init__.py``::

    {"min_api_version": 2}

The downloader reads it before installing and the plugin manager before
importing, so an install that is too old says so instead of failing inside the
plugin's imports. A plugin without the file needs version 1.

Versions:

1. Everything before the manifest existed: the :class:`ImervuePlugin` hooks, the
   language API, ``WorkerHostMixin``, ``Imervue.gui._apply_save.load_rgba``.
2. ``Imervue.plugin.tool_dialog`` (``ToolDialogMixin``, ``show_toast``) and the
   develop-renderer registry ``Imervue.image.develop_backends``.

Raise :data:`PLUGIN_API_VERSION` when the main program gains something plugins
import, and list it here.
"""
from __future__ import annotations

import json
from pathlib import Path

PLUGIN_API_VERSION = 2
MANIFEST_NAME = "plugin.json"
MIN_API_KEY = "min_api_version"


class IncompatiblePluginError(ValueError):
    """A plugin needs a newer plugin API than this Imervue provides."""

    def __init__(self, plugin: str, needed: int):
        super().__init__(
            f"Plugin '{plugin}' needs plugin API {needed}; this Imervue provides "
            f"{PLUGIN_API_VERSION}. Update Imervue to use it.")
        self.plugin = plugin
        self.needed = needed


def required_api_version(plugin_dir: Path) -> int:
    """The plugin API version the plugin in *plugin_dir* needs: 1 without a ``plugin.json``.

    Raises ``ValueError`` for a manifest that is not a JSON object or whose
    ``min_api_version`` is not a whole number of at least 1, and ``OSError`` if
    it exists but cannot be read.
    """
    try:
        text = (plugin_dir / MANIFEST_NAME).read_text(encoding="utf-8")
    except FileNotFoundError:
        return 1
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{MANIFEST_NAME} must hold a JSON object")
    needed = data.get(MIN_API_KEY, 1)
    if isinstance(needed, bool) or not isinstance(needed, int) or needed < 1:
        raise ValueError(f"{MANIFEST_NAME}: {MIN_API_KEY} must be a whole number of at least 1")
    return needed


def check_compatible(plugin_dir: Path, plugin: str | None = None) -> None:
    """Raise :class:`IncompatiblePluginError` if the plugin in *plugin_dir* needs a newer API.

    *plugin* names it in the message (default: the directory name). A
    malformed manifest raises ``ValueError`` as in :func:`required_api_version`.
    """
    needed = required_api_version(plugin_dir)
    if needed > PLUGIN_API_VERSION:
        raise IncompatiblePluginError(plugin or plugin_dir.name, needed)
