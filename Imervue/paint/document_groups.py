"""Layer groups of the paint document.

Create, delete, rename and populate groups, and set a group's visibility,
opacity, blend mode or lock; deleting a group can keep or remove its member
layers. Pure Python, no Qt; ``PaintDocument`` mixes these methods in.
"""
from __future__ import annotations

from typing import Any

from Imervue.paint.layer_model import GROUP_BLEND_MODES, LayerGroup


class DocumentGroupsMixin:
    """Layer-group operations of :class:`~Imervue.paint.document.PaintDocument`."""

    def groups(self) -> list[LayerGroup]:
        return list(self._groups.values())

    def group(self, name: str) -> LayerGroup | None:
        return self._groups.get(name)

    def create_group(self, name: str, **attrs: Any) -> LayerGroup:
        """Register a fresh layer group. Raises if the name already exists."""
        if name in self._groups:
            raise ValueError(f"group {name!r} already exists")
        group = LayerGroup(name=name, **attrs)
        self._groups[name] = group
        self._notify()
        return group

    def delete_group(self, name: str, *, dissolve: bool = True) -> bool:
        """Remove a group. With ``dissolve`` (default) member layers
        move out to top-level; otherwise they are deleted with the group.
        Returns ``True`` if the group existed."""
        if name not in self._groups:
            return False
        del self._groups[name]
        if dissolve:
            self._dissolve_group_members(name)
        else:
            self._remove_group_members(name)
        self._notify()
        return True

    def _dissolve_group_members(self, name: str) -> None:
        """Move every layer in the deleted group out to top-level."""
        for layer in self._layers:
            if layer.group == name:
                layer.group = None

    def _remove_group_members(self, name: str) -> None:
        """Drop every layer that belonged to the deleted group, then
        rebind the active index and the reference-layer index so they
        still point at a real (or ``None``) layer."""
        ref_layer = (
            self._layers[self._reference_layer_index]
            if self._reference_layer_index is not None
            else None
        )
        self._layers = [layer for layer in self._layers if layer.group != name]
        if not self._layers:
            self._active_index = -1
        else:
            self._active_index = max(
                0, min(self._active_index, len(self._layers) - 1),
            )
        if ref_layer is None or ref_layer not in self._layers:
            self._reference_layer_index = None
        else:
            self._reference_layer_index = self._layers.index(ref_layer)

    def set_layer_group(
        self, index: int = -1, *, group: str | None,
    ) -> bool:
        """Move a layer into a group (or out, with ``group=None``)."""
        layer = self._resolve_layer(index)
        if layer is None:
            return False
        if group is not None and group not in self._groups:
            raise ValueError(f"unknown group {group!r}")
        if layer.group == group:
            return False
        layer.group = group
        self._notify()
        return True

    def set_group_attribute(self, group_name: str, **kwargs: Any) -> bool:
        """Update one or more attributes on a layer group.

        ``group_name`` is the lookup key. Pass attribute updates as
        keyword arguments; ``name=`` is rejected here so renames must
        go through :meth:`rename_group`.
        """
        group = self._groups.get(group_name)
        if group is None:
            raise ValueError(f"unknown group {group_name!r}")
        changed = False
        for key, value in kwargs.items():
            if not hasattr(group, key) or key == "name":
                raise ValueError(f"unknown / immutable group attribute {key!r}")
            new_value = value
            if key == "opacity":
                new_value = max(0.0, min(1.0, float(value)))
            elif key == "blend_mode" and value not in GROUP_BLEND_MODES:
                raise ValueError(
                    f"unknown group blend_mode {value!r}; "
                    f"expected one of {GROUP_BLEND_MODES}",
                )
            if getattr(group, key) != new_value:
                setattr(group, key, new_value)
                changed = True
        if changed:
            self._notify()
        return changed

    def rename_group(self, old_name: str, new_name: str) -> bool:
        """Rename a group, updating every member layer's tag. Returns
        ``True`` if the rename took effect."""
        if old_name == new_name:
            return False
        if old_name not in self._groups:
            raise ValueError(f"unknown group {old_name!r}")
        if new_name in self._groups:
            raise ValueError(f"group {new_name!r} already exists")
        if not str(new_name).strip():
            raise ValueError("new group name must be non-empty")
        group = self._groups.pop(old_name)
        # Dataclass field assignment — LayerGroup is mutable.
        group.name = new_name
        self._groups[new_name] = group
        for layer in self._layers:
            if layer.group == old_name:
                layer.group = new_name
        self._notify()
        return True
