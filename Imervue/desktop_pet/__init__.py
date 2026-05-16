"""Desktop Pet — the frameless, transparent, always-on-top puppet
overlay (Tab 5).

The in-tab UI is the control panel (rig picker, driver toggles,
visibility / click-through / size presets); the actual character
lives in a separate top-level :class:`PetWindow` that hosts a
:class:`Imervue.puppet.canvas.PuppetCanvas` in pet mode (transparent
clear, no checker backdrop, alpha buffer in the surface format).
The puppet runtime (parameters, motions, expressions, physics,
live drivers) is reused as-is from the Puppet tab.
"""

from Imervue.desktop_pet.edge_snap import snap_to_screen_edges
from Imervue.desktop_pet.pet_window import PetWindow
from Imervue.desktop_pet.pet_workspace import PetWorkspace
from Imervue.desktop_pet.tray_icon import PetTrayIcon

__all__ = ["PetTrayIcon", "PetWindow", "PetWorkspace", "snap_to_screen_edges"]
