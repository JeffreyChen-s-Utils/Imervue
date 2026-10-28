"""Owned saved selections and restoration."""
from __future__ import annotations

import numpy as np


class DocumentNamedSelectionsMixin:
    """Owned saved selections and restoration."""

    def save_selection(self, name: str) -> bool:
        """Store the current selection under ``name``. Returns ``True``
        if a selection was actually saved (False if there's no active
        selection or the supplied name is blank)."""
        if not str(name).strip():
            raise ValueError("named-selection name must be non-empty")
        if self._selection is None:
            return False
        self._named_selections[name] = self._selection.copy()
        self._notify()
        return True

    def load_selection(self, name: str) -> bool:
        """Restore the selection previously saved as ``name``."""
        mask = self._named_selections.get(name)
        if mask is None:
            return False
        if self.shape is not None and mask.shape != self.shape:
            raise ValueError(
                f"named selection {name!r} shape {mask.shape} does not "
                f"match document {self.shape}",
            )
        self.set_selection(mask.copy())
        return True

    def delete_named_selection(self, name: str) -> bool:
        """Forget a saved selection. Returns ``True`` if it existed."""
        if name not in self._named_selections:
            return False
        del self._named_selections[name]
        self._notify()
        return True

    def list_named_selections(self) -> list[str]:
        return list(self._named_selections.keys())

    def named_selection(self, name: str) -> np.ndarray | None:
        mask = self._named_selections.get(name)
        return mask.copy() if mask is not None else None
