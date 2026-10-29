"""Qt-free layer-stack helpers behind the layers dialog.

Reorder, append-with-defaults and the one-line row summary operate on plain
``Layer`` lists, so they can be unit-tested without instantiating Qt.
"""
from __future__ import annotations

from Imervue.image.layers import (
    DEFAULT_OPACITY,
    LAYER_KINDS,
    MAX_LAYERS,
    Layer,
)


def move_layer_up(layers: list[Layer], idx: int) -> int:
    """Swap ``layers[idx]`` with ``layers[idx-1]``. Returns the new index."""
    if idx <= 0 or idx >= len(layers):
        return idx
    layers[idx - 1], layers[idx] = layers[idx], layers[idx - 1]
    return idx - 1


def move_layer_down(layers: list[Layer], idx: int) -> int:
    """Swap ``layers[idx]`` with ``layers[idx+1]``. Returns the new index."""
    if idx < 0 or idx >= len(layers) - 1:
        return idx
    layers[idx + 1], layers[idx] = layers[idx], layers[idx + 1]
    return idx + 1


def add_default_layer(layers: list[Layer], kind: str = "text") -> Layer | None:
    """Append a default-configured layer of ``kind``. Respects MAX_LAYERS."""
    if len(layers) >= MAX_LAYERS:
        return None
    if kind not in LAYER_KINDS:
        kind = "text"
    layer = Layer(
        kind=kind,
        enabled=True,
        opacity=DEFAULT_OPACITY,
        blend_mode="normal",
        params=_default_params(kind),
    )
    layers.append(layer)
    return layer


def _default_params(kind: str) -> dict:
    if kind == "text":
        return {
            "text": "",
            "corner": "bottom-right",
            "color": [255, 255, 255],
            "font_fraction": 0.035,
            "shadow": True,
        }
    if kind == "image":
        return {"path": ""}
    if kind == "lut":
        return {"path": "", "intensity": 1.0}
    return {}


def _describe_layer(layer: Layer) -> str:
    """Human-readable one-line summary for the list row."""
    suffix = ""
    if layer.kind == "text":
        suffix = layer.params.get("text", "") or "(empty)"
    elif layer.kind in ("image", "lut"):
        path = layer.params.get("path", "") or "(none)"
        # Show only the filename to keep the row narrow
        suffix = path.replace("\\", "/").rsplit("/", 1)[-1] or path
    enabled_marker = "" if layer.enabled else " [off]"
    return (
        f"{layer.kind.title()} • {layer.blend_mode} • "
        f"{int(layer.opacity * 100)}% — {suffix}{enabled_marker}"
    )
