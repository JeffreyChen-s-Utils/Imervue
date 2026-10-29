"""Document binding of the paint canvas.

Loading an image or a blank sheet into a fresh :class:`PaintDocument`,
swapping in another page's document, the listener that forces a texture
re-upload on wholesale mutations, and the selection mask with its marquee
outline. ``PaintCanvas`` mixes these methods in; the signals they emit
(``image_loaded``, ``document_changed``) stay declared on the widget.
"""
from __future__ import annotations

import numpy as np

from Imervue.paint.damage import EMPTY as EMPTY_DAMAGE
from Imervue.paint.document import PaintDocument
from Imervue.paint.marquee import selection_outline_segments

DEFAULT_CANVAS_WIDTH = 1024
DEFAULT_CANVAS_HEIGHT = 1024
DEFAULT_CANVAS_FILL = (255, 255, 255, 255)


class PaintCanvasDocumentMixin:
    """Bind, replace and query the canvas's :class:`PaintDocument`."""

    def new_blank_document(
        self,
        width: int = DEFAULT_CANVAS_WIDTH,
        height: int = DEFAULT_CANVAS_HEIGHT,
        fill: tuple[int, int, int, int] = DEFAULT_CANVAS_FILL,
    ) -> None:
        """Replace the canvas with a fresh ``height``×``width`` Background
        layer filled with ``fill`` (RGBA, 0–255).

        Without this helper a freshly-constructed PaintCanvas has zero
        layers, so :meth:`current_image` returns ``None`` and the tool
        dispatcher silently no-ops on the first brush stroke. The
        workspace calls this from ``__init__`` so the user can paint
        immediately, matching raster paint apps' "open with a blank canvas"
        behaviour.
        """
        if width <= 0 or height <= 0:
            raise ValueError(
                f"canvas size must be positive, got {width}×{height}",
            )
        if len(fill) != 4 or any(not 0 <= int(c) <= 255 for c in fill):
            raise ValueError(
                f"fill must be a 4-tuple of 0..255 ints, got {fill!r}",
            )
        arr = np.empty((int(height), int(width), 4), dtype=np.uint8)
        arr[..., :] = fill
        self.load_image(arr)

    def load_image(self, arr: np.ndarray | None) -> None:
        """Replace the canvas with a single-layer document of ``arr``.

        ``None`` clears the document — the canvas paints empty until
        another image is loaded.
        """
        if arr is None:
            # Re-subscribe to the new empty document so wholesale
            # mutations on it (a fresh add_layer, etc.) trigger the
            # texture-upload listener.
            self._document_unsubscribe()
            self._document = PaintDocument()
            self._document_unsubscribe = self._document.listen(
                self._on_document_changed,
            )
            self._needs_upload = True
            self._pending_damage = EMPTY_DAMAGE
            self._marquee_segments = None
            self._marquee_timer.stop()
            self._user_view_locked = False
            self._rotation_deg = 0.0
            self.update()
            return
        if arr.ndim != 3 or arr.shape[2] != 4 or arr.dtype != np.uint8:
            raise ValueError(
                f"PaintCanvas.load_image expects HxWx4 uint8 RGBA, "
                f"got {arr.shape} {arr.dtype}",
            )
        self._document_unsubscribe()
        self._document = PaintDocument()
        self._document_unsubscribe = self._document.listen(
            self._on_document_changed,
        )
        self._document.load_image(arr)
        self._marquee_segments = None
        self._marquee_timer.stop()
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE
        self._user_view_locked = False
        self._reset_view_to_fit()
        self.image_loaded.emit(arr.shape[1], arr.shape[0])
        self.document_changed.emit()
        self.update()

    def document(self) -> PaintDocument:
        return self._document

    def set_document(self, document: PaintDocument) -> None:
        """Swap the canvas's bound :class:`PaintDocument`.

        Used by the comic-project page browser so picking a different
        page hands the canvas a different document without going
        through the load-image path. The composite cache, marquee
        animation, and texture upload are all reset because the new
        document's pixels are distinct from the previous one's.
        """
        if document is self._document:
            return
        self._document_unsubscribe()
        self._document = document
        self._document_unsubscribe = document.listen(
            self._on_document_changed,
        )
        self._marquee_segments = None
        self._marquee_timer.stop()
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE
        shape = document.shape
        if shape is not None:
            self.image_loaded.emit(shape[1], shape[0])
        self.update()

    def current_image(self) -> np.ndarray | None:
        """Return the *active layer's* image — the buffer tools paint into.

        Returning the active layer (rather than the composited frame)
        is what makes layer-aware painting work: every tool mutates the
        active layer in place, and the canvas re-composites on the
        next paint.
        """
        layer = self._document.active_layer()
        return None if layer is None else layer.image

    def current_selection(self) -> np.ndarray | None:
        return self._document.selection()

    def invalidate_texture(self) -> None:
        """Mark the GL texture for full re-upload on the next paint.

        Used after wholesale document mutations (undo / redo, file
        load) so the canvas's GL texture reflects the new pixels
        instead of the previous frame's cache.
        """
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE

    def _on_document_changed(self) -> None:
        """Subscriber for the active PaintDocument's _notify pulses.

        Forces a full texture re-upload on the next paint and queues
        a repaint. Triggered by add / remove / move / duplicate
        layer, set_layer_attribute, merge / flatten, transform, and
        any other wholesale mutation the document signals through
        :meth:`PaintDocument.listen`.
        """
        self._needs_upload = True
        self._pending_damage = EMPTY_DAMAGE
        self.update()

    def set_selection(self, mask: np.ndarray | None) -> None:
        if mask is not None and (mask.ndim != 2 or mask.dtype != np.bool_):
            raise ValueError(
                f"selection mask must be HxW bool, got {mask.shape} {mask.dtype}",
            )
        self._document.set_selection(mask)
        if mask is None:
            self._marquee_segments = None
            self._marquee_timer.stop()
        else:
            self._marquee_segments = selection_outline_segments(mask)
            if self._marquee_segments.shape[0] > 0:
                self._marquee_timer.start()
            else:
                self._marquee_timer.stop()
        self.update()
