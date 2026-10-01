"""The optional Puppet and Desktop Pet tabs: their settings, and no main-program module loading them early."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from Imervue.gui import optional_tabs
from Imervue.gui.optional_tabs import DESKTOP_PET_TAB, PUPPET_TAB
from Imervue.user_settings.user_setting_dict import user_setting_dict

_ROOT = Path(__file__).resolve().parents[1] / "Imervue"
_OPTIONAL_PACKAGES = ("Imervue.puppet", "Imervue.desktop_pet")
# The two packages themselves, and the MCP server, which reads .puppet files with the
# Qt-free puppet modules; everything else imports them only inside a function.
_ALLOWED = ("puppet", "desktop_pet", "mcp_server")


@pytest.mark.parametrize("key", [PUPPET_TAB, DESKTOP_PET_TAB])
def test_tabs_are_on_unless_turned_off(key):
    assert optional_tabs.tab_enabled(key) is True
    optional_tabs.set_tab_enabled(key, False)
    assert user_setting_dict[key] is False
    assert optional_tabs.tab_enabled(key) is False
    optional_tabs.set_tab_enabled(key, True)
    assert optional_tabs.tab_enabled(key) is True


def test_only_the_two_optional_tabs_can_be_turned_off():
    with pytest.raises(ValueError, match="not an optional tab"):
        optional_tabs.set_tab_enabled("paint_tab_enabled", False)


@pytest.mark.parametrize("shown", [True, False])
def test_pet_shows_on_launch_follows_the_pet_setting(shown):
    from Imervue.desktop_pet import settings as pet_settings
    pet_settings.update(show_on_launch=shown)
    assert optional_tabs.pet_shows_on_launch() is shown


def _module_level_imports(tree: ast.Module):
    """Imports outside any function or ``if TYPE_CHECKING:`` block."""
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
            continue
        guarded = isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test)
        if isinstance(node, (ast.If, ast.Try, ast.With)) and not guarded:
            yield from (n for n in ast.walk(node) if isinstance(n, (ast.Import, ast.ImportFrom)))


def _imported_names(node) -> list[str]:
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return [module] + [f"{module}.{alias.name}" for alias in node.names]
    return [alias.name for alias in node.names]


def test_no_main_program_module_imports_puppet_or_desktop_pet_when_it_loads():
    offenders = []
    for path in sorted(_ROOT.rglob("*.py")):
        relative = path.relative_to(_ROOT)
        if relative.parts[0] in _ALLOWED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _module_level_imports(tree):
            if any(name.startswith(_OPTIONAL_PACKAGES) for name in _imported_names(node)):
                offenders.append(f"{relative.as_posix()}:{node.lineno}")
    assert offenders == []
