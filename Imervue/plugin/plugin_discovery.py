"""Plugin discovery: find candidates, gate on the plugin API, import, pick the plugin class.

Every step is sandboxed: a plugin that cannot be read, imported or recognised
is logged, given a ``failed`` status row and skipped, so one broken plugin never
stops the others. Used by :mod:`Imervue.plugin.plugin_manager`.
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

from Imervue.plugin.plugin_api import MANIFEST_NAME, IncompatiblePluginError, check_compatible
from Imervue.plugin.plugin_base import ImervuePlugin
from Imervue.plugin.status import status_registry

logger = logging.getLogger("Imervue.plugin")


def _plugin_candidates(plugin_dirs: list[Path]) -> Iterator[Path]:
    """Yield each plugin package directory and single-file plugin, in name order.

    Each existing directory is put on ``sys.path`` first, so plugins import
    their own modules as ``<plugin_name>.<module>``.
    """
    for plugin_dir in plugin_dirs:
        if not plugin_dir.is_dir():
            logger.info(f"Plugin directory does not exist, skipping: {plugin_dir}")
            continue

        # Add plugin dir to sys.path so imports work
        dir_str = str(plugin_dir)
        if dir_str not in sys.path:
            sys.path.insert(0, dir_str)

        yield from filter(_is_plugin_candidate, sorted(plugin_dir.iterdir()))


def _is_plugin_candidate(path: Path) -> bool:
    """A package directory with an ``__init__.py``, or a ``.py`` file other than ``__init__``."""
    if path.is_dir():
        return (path / "__init__.py").exists()
    return path.is_file() and path.suffix == ".py" and path.stem != "__init__"


def _api_compatible(candidate: Path) -> bool:
    """False, with the reason logged, for a plugin package this Imervue is too old for.

    A ``plugin.json`` that cannot be read or parsed also keeps the plugin out:
    what it needs is unknown.
    """
    if not candidate.is_dir():
        return True
    try:
        check_compatible(candidate)
    except IncompatiblePluginError as e:
        logger.warning("%s", e)
        return False
    except (OSError, ValueError) as e:
        logger.exception("Skipping plugin '%s': unreadable %s: %s",
                         candidate.name, MANIFEST_NAME, e)
        return False
    return True


def _import_plugin(candidate: Path) -> ModuleType | None:
    """Import a plugin package (cached by ``importlib``) or execute a single-file plugin."""
    if candidate.is_dir():
        module_name = candidate.name
        logger.info("Importing plugin package '%s' from %s", module_name, candidate)
        module = importlib.import_module(module_name)
        logger.info("Successfully imported '%s', registering...", module_name)
        return module
    module_name = candidate.stem
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if not (spec and spec.loader):
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _plugin_class_in(module: ModuleType, source: Path) -> type[ImervuePlugin] | None:
    """Return the module's ``plugin_class``, else its first ImervuePlugin subclass."""
    plugin_class = getattr(module, "plugin_class", None)

    if plugin_class is None:
        # Search for ImervuePlugin subclasses in the module
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                    and issubclass(attr, ImervuePlugin)
                    and attr is not ImervuePlugin):
                plugin_class = attr
                break

    if plugin_class is None:
        logger.warning(f"No plugin class found in '{source}', skipping.")
        return None

    if not (isinstance(plugin_class, type) and issubclass(plugin_class, ImervuePlugin)):
        logger.warning(
            f"plugin_class in '{source}' is not a subclass of ImervuePlugin, skipping."
        )
        return None
    return plugin_class


def _plugin_classes(plugin_dirs: list[Path], *,
                    scope: str = "startup") -> Iterator[type[ImervuePlugin]]:
    """Import every plugin under ``plugin_dirs`` and yield its plugin class.

    A plugin that fails to import, or needs a newer plugin API
    (``Imervue.plugin.plugin_api``), is logged and skipped, so one broken plugin
    never stops the others from loading.
    """
    for candidate in _plugin_candidates(plugin_dirs):
        if not _api_compatible(candidate):
            status_registry.publish(scope + ":" + candidate.name, candidate.name, "failed",
                                    "Incompatible plugin API; update Imervue or the plugin",
                                    scope=scope)
            continue
        try:
            module = _import_plugin(candidate)
            plugin_class = None if module is None else _plugin_class_in(module, candidate)
        except Exception as e:  # plugin sandboxing: any import-time error
            status_registry.publish(scope + ":" + candidate.name, candidate.name, "failed",
                                    str(e) or type(e).__name__, scope=scope)
            logger.exception(f"Failed to load plugin '{candidate.name}': {e}")
            continue
        if plugin_class is not None:
            yield plugin_class
        else:
            status_registry.publish(scope + ":" + candidate.name, candidate.name, "failed",
                                    "No valid ImervuePlugin class", scope=scope)


def _register_languages_of(plugin_class: type[ImervuePlugin]) -> None:
    """Run ``plugin_class.register_languages``; a failure is logged and the plugin still loads."""
    try:
        plugin_class.register_languages()
    except Exception as e:  # plugin sandboxing
        logger.exception(f"[{plugin_class.plugin_name}] register_languages error: {e}")
