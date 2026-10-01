"""Desktop Pet — the frameless, transparent, always-on-top puppet
overlay (Tab 5).

The in-tab UI is the control panel (rig picker, driver toggles,
visibility / click-through / size presets); the actual character
lives in a separate top-level :class:`PetWindow` that hosts a
:class:`Imervue.puppet.canvas.PuppetCanvas` in pet mode (transparent
clear, no checker backdrop, alpha buffer in the surface format).
The puppet runtime (parameters, motions, expressions, physics,
live drivers) is reused as-is from the Puppet tab.

The names below are imported on first use through module ``__getattr__``,
as ``Imervue.puppet`` does: importing a light submodule such as
``Imervue.desktop_pet.settings`` runs this file, and must not drag in the pet
window, its workspace and the Puppet canvas with it.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.desktop_pet.edge_snap import snap_to_screen_edges
    from Imervue.desktop_pet.pet_script import (
        PetScript,
        PetScriptEngine,
        PetScriptError,
        load_script,
        save_script,
    )
    from Imervue.desktop_pet.pet_window import PetWindow
    from Imervue.desktop_pet.pet_workspace import PetWorkspace
    from Imervue.desktop_pet.tray_icon import PetTrayIcon

#: The exports that live in ``pet_script``; every other one has a module of its own.
_SCRIPT_NAMES = frozenset({"PetScript", "PetScriptEngine", "PetScriptError", "load_script",
                           "save_script"})

__all__ = [
    "PetScript",
    "PetScriptEngine",
    "PetScriptError",
    "PetTrayIcon",
    "PetWindow",
    "PetWorkspace",
    "load_script",
    "save_script",
    "snap_to_screen_edges",
]


def _home(name: str):
    """The submodule that defines export *name*, imported on this first use."""
    if name in _SCRIPT_NAMES:
        from Imervue.desktop_pet import pet_script as home
    elif name == "PetTrayIcon":
        from Imervue.desktop_pet import tray_icon as home
    elif name == "PetWindow":
        from Imervue.desktop_pet import pet_window as home
    elif name == "PetWorkspace":
        from Imervue.desktop_pet import pet_workspace as home
    elif name == "snap_to_screen_edges":
        from Imervue.desktop_pet import edge_snap as home
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return home


def __getattr__(name: str):
    return getattr(_home(name), name)
