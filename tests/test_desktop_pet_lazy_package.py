"""``Imervue.desktop_pet`` exports its classes lazily, so a light submodule loads alone."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from Imervue import desktop_pet

_ROOT = Path(__file__).resolve().parents[1]
_HEAVY = ("Imervue.desktop_pet.pet_window", "Imervue.desktop_pet.pet_workspace",
          "Imervue.desktop_pet.tray_icon", "Imervue.puppet.canvas")


def _loaded_after(statement: str) -> list[str]:
    """The heavy modules a fresh interpreter has loaded after running *statement*."""
    probe = f"import json, sys; {statement}; print(json.dumps([m for m in {_HEAVY!r} if m in sys.modules]))"
    done = subprocess.run([sys.executable, "-c", probe], cwd=_ROOT, capture_output=True, text=True,
                          timeout=120, check=True)
    return json.loads(done.stdout.strip())


def test_importing_the_settings_loads_no_window_workspace_or_canvas():
    assert _loaded_after("import Imervue.desktop_pet.settings") == []


def test_importing_the_package_loads_nothing_heavy():
    assert _loaded_after("import Imervue.desktop_pet") == []


def test_a_name_is_imported_when_first_used():
    from Imervue.desktop_pet.pet_workspace import PetWorkspace
    assert desktop_pet.PetWorkspace is PetWorkspace


@pytest.mark.parametrize("name", desktop_pet.__all__)
def test_every_exported_name_resolves(name):
    assert getattr(desktop_pet, name) is not None


def test_an_unknown_name_is_an_attribute_error():
    with pytest.raises(AttributeError, match="no attribute 'Nope'"):
        _ = desktop_pet.Nope
