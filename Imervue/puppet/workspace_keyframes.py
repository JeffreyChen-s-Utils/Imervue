"""Workspace keyframe editing and canvas editing notifications."""
from __future__ import annotations
from Imervue.puppet.operations import (
    remove_key,
    set_key_at_value,
    snapshot_current_forms,
)

class PuppetKeyframesMixin:
    def set_key_at_current_slider(self, param_id: str) -> bool:
        """Snapshot current deformer forms at the slider's current
        value and write them as a key on ``param_id``. Wired by the
        parameter dock's per-row Set Key button."""
        doc = self._canvas.document()
        if doc is None:
            return False
        value = self._canvas.parameter_values().get(param_id)
        if value is None:
            return False
        forms = snapshot_current_forms(doc)
        ok = set_key_at_value(doc, param_id, value, forms)
        if ok:
            self._announce(
                "puppet_key_set", "Set key on {id} at {value:.2f}",
                id=param_id, value=value,
            )
        return ok

    def remove_key_at_current_slider(self, param_id: str) -> bool:
        doc = self._canvas.document()
        if doc is None:
            return False
        value = self._canvas.parameter_values().get(param_id)
        if value is None:
            return False
        ok = remove_key(doc, param_id, value)
        if ok:
            self._canvas.load_document(doc)   # re-evaluate at neutral keys
            self._canvas.set_parameter_value(param_id, value)
            self._announce(
                "puppet_key_removed", "Removed key from {id} at {value:.2f}",
                id=param_id, value=value,
            )
        return ok

    def _toggle_mesh_edit(self, enabled: bool) -> None:
        self._canvas.set_mesh_edit_enabled(enabled)
        self._announce(
            "puppet_mesh_edit_on" if enabled else "puppet_mesh_edit_off",
            "Mesh editing on" if enabled else "Mesh editing off",
        )

    def _on_bone_hierarchy_changed(self) -> None:
        """Re-render the canvas after a reparent so the new FK order
        is reflected on screen without a manual reload."""
        doc = self._canvas.document()
        if doc is not None:
            self._canvas.load_document(doc)
