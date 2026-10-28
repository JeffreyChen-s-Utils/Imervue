"""PaintDocument — layer stack + selection + active layer.

The Paint workspace draws against a single document. Tools mutate
``document.active_layer().image`` in place, the document broadcasts a
"changed" signal-via-callback, and the canvas re-composites the stack
on the next paint.

Pure-Python; no Qt dependency. The layer dock subscribes to the
``listen`` callback to refresh its visible state. The document also
caches the last composite so painting one stroke doesn't pay
N-times-the-work to recomposite — only the cache is invalidated; the
canvas's next paint pays the recomposite cost once.
"""
from __future__ import annotations

import copy
from collections.abc import Callable

import numpy as np

from Imervue.paint.compositing import LAYER_BLEND_MODES, composite_stack
from Imervue.paint.document_composite import DocumentCompositeMixin
from Imervue.paint.document_geometry import DocumentGeometryMixin
from Imervue.paint.document_groups import DocumentGroupsMixin

# Layer model lives in layer_model; re-exported here so existing
# ``from Imervue.paint.document import Layer, LayerGroup`` imports keep working.
from Imervue.paint.document_layer_access import DocumentLayerAccessMixin
from Imervue.paint.document_layer_creation import DocumentLayerCreationMixin
from Imervue.paint.document_layer_order import DocumentLayerOrderMixin
from Imervue.paint.document_layer_properties import DocumentLayerPropertiesMixin
from Imervue.paint.document_masks import DocumentMasksMixin
from Imervue.paint.document_merge import DocumentMergeMixin
from Imervue.paint.document_named_selections import DocumentNamedSelectionsMixin
from Imervue.paint.document_reference import DocumentReferenceMixin
from Imervue.paint.document_selection import DocumentSelectionMixin
from Imervue.paint.document_state import DocumentStateMixin
from Imervue.paint.layer_model import (
    BACKGROUND_LAYER_NAME,
    DEFAULT_LAYER_NAME,
    GROUP_BLEND_MODES,
    LAYER_LABELS,
    Layer,
    LayerGroup,
)

__all__ = [
    "LAYER_BLEND_MODES",
    "composite_stack",
    "BACKGROUND_LAYER_NAME",
    "DEFAULT_LAYER_NAME",
    "GROUP_BLEND_MODES",
    "LAYER_LABELS",
    "Layer",
    "LayerGroup",
    "PaintDocument",
]


_CONTENT_FIELDS = (
    "_layers", "_active_index", "_selection", "_groups", "_named_selections",
    "_reference_layer_index", "panel_layout",
)


class PaintDocument(
    DocumentLayerAccessMixin,
    DocumentReferenceMixin,
    DocumentStateMixin,
    DocumentLayerCreationMixin,
    DocumentLayerOrderMixin,
    DocumentLayerPropertiesMixin,
    DocumentMasksMixin,
    DocumentSelectionMixin,
    DocumentNamedSelectionsMixin,
    DocumentCompositeMixin,
    DocumentGroupsMixin, DocumentMergeMixin, DocumentGeometryMixin,
):
    """Layer stack + active-layer pointer + selection mask.

    ``shape`` is ``(height, width)`` — every layer added must match it.
    The document is empty until :meth:`load_image` or :meth:`add_layer`
    runs.
    """

    def __init__(self):
        self._layers: list[Layer] = []
        self._active_index: int = -1
        self._selection: np.ndarray | None = None
        self._composite_cache: np.ndarray | None = None
        # Optional bounding rect (x, y, w, h) inside the cached
        # composite that has been touched since the last full
        # rebuild. Populated by ``mark_composite_dirty`` so brush
        # strokes can patch only the dirty region instead of
        # recomputing every layer over the entire canvas.
        self._composite_dirty_rect: tuple[int, int, int, int] | None = None
        self._listeners: list[Callable[[], None]] = []
        self._groups: dict[str, LayerGroup] = {}
        self._named_selections: dict[str, np.ndarray] = {}
        # Index of the layer the bucket fill samples for connectivity /
        # tolerance — raster paint apps' "Reference Layer" toggle. ``None`` means
        # the bucket samples its own target layer (the legacy default).
        # Stored as an index, not a Layer reference, so it survives
        # reorderings via the helpers below.
        self._reference_layer_index: int | None = None
        # The manga panel layout Panel Cutter drew last (``manga_panels.PanelLayout``),
        # which the brush's Snap to panel clips strokes to; native saves preserve it.
        self.panel_layout = None

    def __deepcopy__(self, memo: dict) -> PaintDocument:
        """Deep-copy the document CONTENT, not its runtime wiring.

        ``_listeners`` hold bound methods of Qt widgets (the canvas, the layers
        dock); the default deepcopy walks them into the widget tree and raises
        ``TypeError: cannot pickle ...`` — which crashed "Duplicate page" — and
        even when a listener survives copying, the clone would notify the
        ORIGINAL page's widgets. A cloned document starts with no listeners and
        cold composite caches; only the layer stack, groups, selections and
        indices carry over.
        """
        clone = type(self)()
        memo[id(self)] = clone
        for name in _CONTENT_FIELDS:
            setattr(clone, name, copy.deepcopy(getattr(self, name), memo))
        return clone

    def adopt_content(self, source: PaintDocument) -> None:
        """Install owned content and notify once, keeping identity and listeners.

        The caller transfers an independent copy and must not mutate it again.
        """
        for name in _CONTENT_FIELDS:
            setattr(self, name, getattr(source, name))
        self._notify()

    def listen(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(callback)

        def _unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)
        return _unsubscribe

    def _notify(self) -> None:
        self._composite_cache = None
        self._composite_dirty_rect = None
        self._emit_changed()

    def _emit_changed(self) -> None:
        """Notify the listener snapshot, allowing subscription changes in callbacks."""
        for callback in self._listeners.copy():
            callback()
