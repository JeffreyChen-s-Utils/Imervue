"""Material-library drops for the Paint workspace.

Routes a material picked in the Materials dock by category: poses paste
as a fitted layer, textures / tones / patterns tile across the canvas, and
brush tips bind to the active brush. Extracted from
:mod:`workspace_content` and composed into :class:`ContentOpsMixin` via
:class:`MaterialDropMixin`.
"""
from __future__ import annotations

import numpy as np

_TILE_CATEGORIES = ("texture", "tone", "pattern")


class MaterialDropMixin:
    """Drop Materials-dock entries onto the active document.

    Expects the host to provide ``_canvas``, ``_state`` and
    ``_material_dock``.
    """

    # ---- material drops ------------------------------------------------

    def _on_material_chosen(self, path: str) -> None:
        """Drop a material onto the canvas based on its category.

        * ``pose`` — load full image, fit to canvas, paste into a new layer.
        * ``texture`` / ``tone`` / ``pattern`` — tile across the canvas.
        * ``brush_tip`` — bind the tip PNG to the active brush.
        """
        from pathlib import Path

        from Imervue.paint.material_library import MaterialEntry

        entry = next(
            (e for e in self._material_dock.index().entries
             if str(e.path) == path),
            None,
        )
        if entry is None:
            entry = MaterialEntry(name=Path(path).stem, path=Path(path))
        if entry.category == "pose":
            self._drop_pose_material(entry)
        elif entry.category in _TILE_CATEGORIES:
            self._drop_tile_material(entry)
        elif entry.category == "brush_tip":
            self._drop_brush_tip_material(entry)

    def _drop_brush_tip_material(self, entry) -> None:
        """Bind the picked tip's PNG path to the active brush.

        Procedural ``brush_tip`` entries that don't have an on-disk
        path are silently ignored — the brush engine reads tips from
        a file path, so a virtual entry has nothing to point at.
        """
        if entry.is_procedural():
            return
        path = str(entry.path)
        if not path or path.startswith("procedural://"):
            return
        self._state.set_brush(tip_path=path)

    def _drop_pose_material(self, entry) -> None:
        from Imervue.paint.pose_drop import fit_pose_to_canvas, load_pose_image
        canvas_doc = self._canvas.document()
        if canvas_doc.shape is None:
            return
        try:
            pose = load_pose_image(entry.path)
        except (OSError, ValueError):
            return
        fitted = fit_pose_to_canvas(pose, canvas_doc.shape)
        layer = canvas_doc.add_layer(name=f"Pose · {entry.name}")
        np.copyto(layer.image, fitted)
        from Imervue.paint.workspace_history import commit_document_edit
        commit_document_edit(self)

    def _drop_tile_material(self, entry) -> None:
        """Tile a procedural / on-disk material across the canvas as a
        fresh layer. Honours the active selection: if one exists, the
        tiled fill is masked to it."""
        from Imervue.paint.material_procedural import tile_to_canvas
        canvas_doc = self._canvas.document()
        if canvas_doc.shape is None:
            return
        tile = self._load_material_tile(entry)
        if tile is None:
            return
        h, w = canvas_doc.shape
        filled = tile_to_canvas(tile, (h, w))
        selection = self._canvas.current_selection()
        layer = canvas_doc.add_layer(name=f"{entry.category.title()} · {entry.name}")
        if selection is None:
            np.copyto(layer.image, filled)
        else:
            layer.image[selection] = filled[selection]
        from Imervue.paint.workspace_history import commit_document_edit
        commit_document_edit(self)

    @staticmethod
    def _load_material_tile(entry):
        """Return an HxWx4 RGBA tile for ``entry``, or ``None`` on failure.

        Procedural entries call their provider; path entries are
        decoded via PIL. Both paths validate the array shape before
        returning so the caller can treat ``None`` as "nothing to paste".
        """
        if entry.is_procedural():
            try:
                tile = entry.render()
            except (ValueError, RuntimeError):
                return None
        else:
            from Imervue.image.read_errors import IMAGE_READ_ERRORS
            from Imervue.image.shown import load_shown_rgba
            try:
                tile = load_shown_rgba(entry.path)   # upright and sRGB, like the viewer
            except IMAGE_READ_ERRORS:
                return None
        if (
            tile is None
            or tile.ndim != 3
            or tile.shape[2] != 4
            or tile.dtype != np.uint8
        ):
            return None
        return tile
