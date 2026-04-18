"""
顏色標籤管理
Color labels — per-image colour flag (red / yellow / green / blue / purple),
independent of the 5-star rating system.

Lightroom-style colour organisation: quick visual tagging with F1-F5. Storage
lives under ``user_setting_dict["image_color_labels"]`` as ``{path: color}``
so it serialises cleanly to JSON alongside the other settings.
"""
from __future__ import annotations

from typing import Iterable

# Canonical colour names — single source of truth. Order matches F1-F5.
COLORS = ("red", "yellow", "green", "blue", "purple")

# RGB tuples used by the renderer so the palette stays consistent across
# thumbnails, list view, and status bar.
COLOR_RGB = {
    "red":    (220, 70, 70),
    "yellow": (235, 195, 60),
    "green":  (80, 180, 90),
    "blue":   (80, 140, 220),
    "purple": (170, 100, 210),
}


def _store() -> dict[str, str]:
    """Return the live dict from settings, creating it if absent."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    d = user_setting_dict.get("image_color_labels")
    if not isinstance(d, dict):
        d = {}
        user_setting_dict["image_color_labels"] = d
    return d


def get_color_label(path: str) -> str | None:
    """Return the colour flag for ``path`` or ``None`` if unflagged."""
    if not path:
        return None
    return _store().get(path)


def set_color_label(path: str, color: str | None) -> bool:
    """Set ``path`` to ``color`` (or clear it if ``color`` is None/invalid).

    Returns True if the label changed, False if the call was a no-op. Unknown
    colour names fall back to a clear — we never poison the dict with bogus
    values that the UI can't render.
    """
    if not path:
        return False
    from Imervue.user_settings.user_setting_dict import schedule_save
    store = _store()

    if color is None or color not in COLORS:
        if path in store:
            del store[path]
            schedule_save()
            return True
        return False

    if store.get(path) == color:
        return False
    store[path] = color
    schedule_save()
    return True


def clear_color_label(path: str) -> bool:
    """Remove the colour flag from ``path`` — shortcut for ``set_color_label(path, None)``."""
    return set_color_label(path, None)


def toggle_color_label(path: str, color: str) -> str | None:
    """If ``path`` already has ``color``, clear it; otherwise set it.

    Matches the rating-key behaviour where pressing the same number toggles
    off. Returns the new colour (or None if it was toggled off).
    """
    if not path or color not in COLORS:
        return get_color_label(path)
    current = get_color_label(path)
    if current == color:
        clear_color_label(path)
        return None
    set_color_label(path, color)
    return color


def paths_with_label(color: str | None = None) -> list[str]:
    """Return all paths with ``color`` (or with *any* label if ``color`` is None)."""
    store = _store()
    if color is None:
        return list(store.keys())
    if color not in COLORS:
        return []
    return [p for p, c in store.items() if c == color]


def filter_by_color(paths: Iterable[str], color: str | None) -> list[str]:
    """Filter an iterable of image paths down to those flagged ``color``.

    ``color`` values:
      - ``None`` / ``""`` — return everything (no-op filter)
      - ``"any"`` — keep paths that have any label
      - ``"none"`` — keep paths with no label
      - a valid colour name — exact match
    """
    if not color:
        return list(paths)
    store = _store()
    if color == "any":
        return [p for p in paths if p in store]
    if color == "none":
        return [p for p in paths if p not in store]
    if color not in COLORS:
        return list(paths)
    return [p for p in paths if store.get(p) == color]
