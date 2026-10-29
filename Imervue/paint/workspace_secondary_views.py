"""Secondary preview windows for the Paint workspace.

Opens overview, mirrored and tiled read-only windows onto the active
composite, forgets them when they close, and pushes each new composite
to every open one. Extracted from :mod:`workspace_content` and composed
into :class:`ContentOpsMixin` via :class:`SecondaryViewMixin`.
"""
from __future__ import annotations


class SecondaryViewMixin:
    """Track and refresh the workspace's secondary preview windows.

    Expects the host to provide ``_canvas``.
    """

    # ---- secondary preview windows -------------------------------------

    def open_secondary_view(self):
        """Spawn an independent overview window onto the same composite."""
        return self._open_secondary_view(mirror_horizontal=False)

    def open_mirror_preview(self):
        """Spawn a horizontally-flipped read-only preview window.

        The flip is a view-only transform on the composite so the
        underlying document is unaffected — the "anatomy check" workflow.
        """
        return self._open_secondary_view(mirror_horizontal=True)

    def open_tile_preview(self):
        """Spawn a 3×3 tiled preview window for seamless-tile checking."""
        return self._open_secondary_view(tile_preview=True)

    def _open_secondary_view(
        self, *,
        mirror_horizontal: bool = False,
        tile_preview: bool = False,
    ):
        from Imervue.paint.multi_view import SecondaryView, composite_to_pixmap
        view = SecondaryView(
            self,
            mirror_horizontal=mirror_horizontal,
            tile_preview=tile_preview,
        )
        if not hasattr(self, "_secondary_views"):
            self._secondary_views = []
        self._secondary_views.append(view)
        view.closed.connect(lambda v=view: self._on_secondary_view_closed(v))
        composite = self._canvas.document().composite()
        view.set_composite(composite_to_pixmap(composite))
        view.show()
        return view

    def secondary_view_count(self) -> int:
        return len(getattr(self, "_secondary_views", ()))

    def _on_secondary_view_closed(self, view) -> None:
        if hasattr(self, "_secondary_views") and view in self._secondary_views:
            self._secondary_views.remove(view)

    def _push_composite_to_secondary_views(self, composite) -> None:
        from Imervue.paint.multi_view import composite_to_pixmap
        views = getattr(self, "_secondary_views", ())
        if not views:
            return
        pixmap = composite_to_pixmap(composite)
        for view in views:
            view.set_composite(pixmap)
