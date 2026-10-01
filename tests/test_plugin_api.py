"""Plugin API versions: a plugin's ``plugin.json`` names what it needs, and too new is refused."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from Imervue.plugin.plugin_api import (
    MANIFEST_NAME,
    PLUGIN_API_VERSION,
    IncompatiblePluginError,
    check_compatible,
    required_api_version,
)

_PLUGINS = Path(__file__).resolve().parent.parent / "plugins"
#: Main-program modules added at plugin API 2; a plugin importing one must declare it.
_API_2_MODULES = ("Imervue.plugin.tool_dialog", "Imervue.image.develop_backends")


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / MANIFEST_NAME).write_text(text, encoding="utf-8")
    return tmp_path


def test_a_plugin_without_a_manifest_needs_version_1(tmp_path):
    assert required_api_version(tmp_path) == 1
    check_compatible(tmp_path)


def test_the_manifest_names_the_version(tmp_path):
    assert required_api_version(_write(tmp_path, '{"min_api_version": 2}')) == 2


def test_a_manifest_without_the_key_needs_version_1(tmp_path):
    assert required_api_version(_write(tmp_path, '{"other": true}')) == 1


@pytest.mark.parametrize("text", ["not json", "[2]", '{"min_api_version": "2"}',
                                  '{"min_api_version": 0}', '{"min_api_version": true}',
                                  '{"min_api_version": 2.5}'])
def test_a_malformed_manifest_is_an_error(tmp_path, text):
    with pytest.raises(ValueError, match=r"plugin\.json|Expecting|Extra data"):
        required_api_version(_write(tmp_path, text))


@pytest.mark.parametrize("needed", [1, PLUGIN_API_VERSION])
def test_up_to_this_version_is_accepted(tmp_path, needed):
    check_compatible(_write(tmp_path, json.dumps({"min_api_version": needed})))


def test_a_newer_version_is_refused_with_the_plugin_named(tmp_path):
    folder = _write(tmp_path, json.dumps({"min_api_version": PLUGIN_API_VERSION + 1}))
    with pytest.raises(IncompatiblePluginError) as caught:
        check_compatible(folder, "AI Thing")
    assert caught.value.plugin == "AI Thing"
    assert caught.value.needed == PLUGIN_API_VERSION + 1
    assert "Update Imervue" in str(caught.value)


def test_the_directory_names_the_plugin_by_default(tmp_path):
    folder = tmp_path / "ai_thing"
    folder.mkdir()
    _write(folder, json.dumps({"min_api_version": PLUGIN_API_VERSION + 1}))
    with pytest.raises(IncompatiblePluginError, match="ai_thing"):
        check_compatible(folder)


def _imports(plugin: Path) -> set[str]:
    found = set()
    for path in plugin.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
            elif isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
    return found


@pytest.mark.parametrize("plugin", sorted(p for p in _PLUGINS.iterdir()
                                          if (p / "__init__.py").is_file()), ids=lambda p: p.name)
def test_a_bundled_plugin_using_api_2_declares_it(plugin):
    """Without the manifest an older install downloads it and fails at import time."""
    if _imports(plugin) & set(_API_2_MODULES):
        assert required_api_version(plugin) >= 2
    check_compatible(plugin)
