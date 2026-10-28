"""Visibility of a paint layer within its group."""
from __future__ import annotations

from Imervue.paint.layer_model import Layer, LayerGroup


def layer_effectively_visible(layer: Layer, groups: dict[str, LayerGroup]) -> bool:
    """Visibility considering both the layer flag and any group's flag."""
    if not layer.visible or layer.opacity <= 0:
        return False
    if layer.group is not None and layer.group in groups:
        grp = groups[layer.group]
        if not grp.visible or grp.opacity <= 0:
            return False
    return True
