"""Layer lookup, active selection and name search."""
from __future__ import annotations

from Imervue.paint.layer_model import Layer


class DocumentLayerAccessMixin:
    """Layer lookup, active selection and name search."""

    @property
    def shape(self) -> tuple[int, int] | None:
        if not self._layers:
            return None
        return self._layers[0].image.shape[:2]

    @property
    def layer_count(self) -> int:
        return len(self._layers)

    def layers(self) -> list[Layer]:
        return list(self._layers)

    def layer_at(self, index: int) -> Layer:
        return self._layers[index]

    def active_layer(self) -> Layer | None:
        if 0 <= self._active_index < len(self._layers):
            return self._layers[self._active_index]
        return None

    def active_layer_index(self) -> int:
        return self._active_index

    def set_active_layer(self, index: int) -> None:
        if not (0 <= index < len(self._layers)):
            raise IndexError(f"active layer index {index} out of range")
        if index == self._active_index:
            return
        self._active_index = index
        self._notify()

    def _resolve_layer(self, index: int) -> Layer | None:
        if not self._layers:
            return None
        if index == -1:
            if self._active_index < 0:
                return None
            return self._layers[self._active_index]
        if not 0 <= index < len(self._layers):
            raise IndexError(f"layer index {index} out of range")
        return self._layers[index]

    def find_layers(self, query: str) -> list[int]:
        """Return indices whose names contain every whitespace-separated query token."""
        tokens = query.lower().split()
        return [index for index, layer in enumerate(self._layers)
                if all(token in layer.name.lower() for token in tokens)]
