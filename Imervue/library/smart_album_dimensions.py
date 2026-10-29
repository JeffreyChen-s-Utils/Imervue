"""Pixel-dimension and aspect rules for Smart Albums (header-only reads)."""
from __future__ import annotations


def _aspect_ok(
    width: int, height: int, min_aspect, max_aspect,
) -> bool:
    """True when ``width / height`` falls within the aspect bounds (if any)."""
    if min_aspect is None and max_aspect is None:
        return True
    if height == 0:
        return False
    aspect = width / height
    if min_aspect is not None and aspect < float(min_aspect):
        return False
    return not (max_aspect is not None and aspect > float(max_aspect))


_DIMENSION_KEYS = (
    "min_width", "max_width", "min_height", "max_height",
    "min_aspect", "max_aspect",
)


def _dims_ok(width: int, height: int, rules: dict) -> bool:
    """True when ``width`` / ``height`` satisfy the min/max pixel bounds."""
    min_w, max_w = rules.get("min_width"), rules.get("max_width")
    min_h, max_h = rules.get("min_height"), rules.get("max_height")
    if min_w and width < int(min_w):
        return False
    if max_w and width > int(max_w):
        return False
    if min_h and height < int(min_h):
        return False
    return not (max_h and height > int(max_h))


def _apply_dimension_filters(paths: list[str], rules: dict) -> list[str]:
    """Filter by pixel dimensions (min/max width & height) and aspect.

    Reads only the image header (no full decode) and runs after the cheaper
    filters, so it touches the smallest possible set. Unreadable images can't
    satisfy a dimension rule, so they're dropped.
    """
    if not any(rules.get(key) for key in _DIMENSION_KEYS):
        return paths
    min_aspect, max_aspect = rules.get("min_aspect"), rules.get("max_aspect")
    from Imervue.image.dimensions import image_dimensions
    out: list[str] = []
    for p in paths:
        dims = image_dimensions(p)
        if dims is None:
            continue
        width, height = dims
        if _dims_ok(width, height, rules) and _aspect_ok(
            width, height, min_aspect, max_aspect,
        ):
            out.append(p)
    return out
