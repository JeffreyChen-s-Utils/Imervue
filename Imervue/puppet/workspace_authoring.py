"""Document authoring commands and first-available identifiers."""
from __future__ import annotations
from Imervue.puppet.operations import (
    add_parameter,
    add_rotation_deformer,
    add_warp_deformer,
)

def _first_available_id(existing: set[str], prefix: str) -> str:
    index = 1
    while True:
        candidate = f"{prefix}{index}"
        if candidate not in existing:
            return candidate
        index += 1


def _add_item(workspace, operation, identifier_name, prefix, key, fallback) -> None:
    document = workspace._canvas.document()
    if document is None:
        return
    item_id = getattr(workspace, identifier_name)(prefix)
    if operation(document, item_id):
        workspace._canvas.load_document(document)
        workspace._announce(key, fallback, id=item_id)


class PuppetAuthoringMixin:
    def _add_rotation_deformer(self) -> None:
        _add_item(self, add_rotation_deformer, "_unique_deformer_id", "rotation",
                  "puppet_added_deformer", "Added deformer {id}")

    def _add_warp_deformer(self) -> None:
        _add_item(self, add_warp_deformer, "_unique_deformer_id", "warp",
                  "puppet_added_deformer", "Added deformer {id}")

    def _add_parameter(self) -> None:
        _add_item(self, add_parameter, "_unique_parameter_id", "Param",
                  "puppet_added_parameter", "Added parameter {id}")

    def _unique_deformer_id(self, prefix: str) -> str:
        doc = self._canvas.document()
        existing = {d.id for d in (doc.deformers if doc else [])}
        return _first_available_id(existing, f"{prefix}_")

    def _unique_parameter_id(self, prefix: str) -> str:
        doc = self._canvas.document()
        existing = {p.id for p in (doc.parameters if doc else [])}
        return _first_available_id(existing, prefix)
