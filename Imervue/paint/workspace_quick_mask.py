"""Quick-mask mode for the Paint workspace.

Swaps the active layer's pixels for a paintable selection overlay and
converts it back into a selection on exit, restoring against the document
the mask was entered on. Extracted from :mod:`workspace_content` and
composed into :class:`ContentOpsMixin` via :class:`QuickMaskMixin`.
"""
from __future__ import annotations


class QuickMaskMixin:
    """Enter / exit quick-mask mode on the active layer.

    Expects the host to provide ``canvas()``.
    """

    # ---- quick mask mode -----------------------------------------------

    def is_quick_mask_active(self) -> bool:
        return getattr(self, "_quick_mask_state", None) is not None

    def enter_quick_mask(self) -> bool:
        """Toggle the active layer into a paintable selection overlay.

        Returns ``True`` if the mode was entered. Refuses gracefully
        when there's no active layer (the user has nothing to paint
        on); the caller can ignore the return.
        """
        if self.is_quick_mask_active():
            return False
        from Imervue.paint.quick_mask import enter_mode
        canvas = self.canvas()
        document = canvas.document()
        layer = document.active_layer()
        if layer is None:
            return False
        layer_index = document._active_index   # noqa: SLF001
        state = enter_mode(
            layer.image, document.selection(), layer_index=layer_index,
        )
        # Swap the layer's pixels for the proxy buffer so brushes paint
        # into the overlay rather than the underlying art.
        layer.image = state.buffer
        self._quick_mask_state = state
        # Remember the layer by identity, not index — a layer added / removed /
        # reordered while in quick-mask shifts indices, so restoring by index
        # would write the overlay back into the wrong layer.
        self._quick_mask_layer = layer
        # Remember the owning document too. exit_quick_mask must restore against
        # THIS document, not whatever the active canvas shows — the user can
        # switch tabs (a different canvas/document) while masked, and restoring
        # against the wrong document fails the identity guard and drops the saved
        # original pixels, leaving this layer as the red proxy (artwork lost).
        self._quick_mask_document = document
        document.invalidate_composite()
        canvas.update()
        return True

    def exit_quick_mask(self) -> bool:
        """Convert the painted overlay back into a selection and
        restore the layer's original pixels."""
        if not self.is_quick_mask_active():
            return False
        from Imervue.paint.quick_mask import exit_mode
        state = self._quick_mask_state   # noqa: SLF001
        # Restore against the document the mask was entered on, not the active
        # canvas's — they differ once the user switches tabs while masked.
        document = getattr(self, "_quick_mask_document", None) or self.canvas().document()
        layer = getattr(self, "_quick_mask_layer", None)
        if layer is None or not any(layer is lyr for lyr in document.layers()):
            # The masked layer was removed while in quick-mask mode; drop the
            # state without touching anything (restoring by index could hit a
            # different, reordered layer).
            self._quick_mask_state = None
            self._quick_mask_layer = None
            self._quick_mask_document = None
            return False
        restored, selection = exit_mode(state)
        layer.image = restored
        document.set_selection(selection)
        self._quick_mask_state = None
        self._quick_mask_layer = None
        self._quick_mask_document = None
        document.invalidate_composite()
        self.canvas().update()
        return True
