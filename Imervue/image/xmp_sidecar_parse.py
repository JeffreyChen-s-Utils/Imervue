"""Parse a defusedxml-loaded XMP document into an :class:`XmpData`."""
from __future__ import annotations

from Imervue.image.xmp_sidecar_schema import (
    _LR_HIERARCHY,
    _NS,
    _RATING_MAX,
    _RATING_MIN,
    XmpData,
    _find_descriptions,
)


def _extract_label(desc) -> str:
    """Pull ``xmp:Label`` from the attribute or child element, trimmed."""
    label = desc.get(f"{{{_NS['xmp']}}}Label") or ""
    if not label:
        child = desc.find(f"{{{_NS['xmp']}}}Label")
        label = (child.text or "").strip() if child is not None else ""
    return label.strip()


def _parse_rating(desc) -> int:
    """Pull ``xmp:Rating`` from attributes or child element, clamped to range."""
    raw = desc.get(f"{{{_NS['xmp']}}}Rating")
    if raw is None:
        child = desc.find(f"{{{_NS['xmp']}}}Rating")
        raw = child.text if child is not None else None
    try:
        value = int(float(raw)) if raw is not None else 0
    except (TypeError, ValueError):
        return 0
    return max(_RATING_MIN, min(_RATING_MAX, value))


def _parse_alt_default(elem) -> str:
    """Return the default language text from an ``rdf:Alt`` tree, else ''."""
    if elem is None:
        return ""
    alt = elem.find(f"{{{_NS['rdf']}}}Alt")
    if alt is None:
        return (elem.text or "").strip()
    default = None
    for li in alt.findall(f"{{{_NS['rdf']}}}li"):
        lang = li.get(f"{{{_NS['xml']}}}lang", "")
        if lang in ("", "x-default"):
            default = li.text or ""
            break
        if default is None:
            default = li.text or ""
    return (default or "").strip()


def _parse_bag(elem) -> list[str]:
    """Return the list of text entries in an ``rdf:Bag`` / ``rdf:Seq``."""
    if elem is None:
        return []
    for container_name in ("Bag", "Seq"):
        container = elem.find(f"{{{_NS['rdf']}}}{container_name}")
        if container is not None:
            return [
                (li.text or "").strip()
                for li in container.findall(f"{{{_NS['rdf']}}}li")
                if (li.text or "").strip()
            ]
    return []


def _from_root(root) -> XmpData:
    """The fields Imervue tracks, read from a parsed XMP document."""
    descs = _find_descriptions(root)
    if not descs:
        return XmpData()

    # Merge across all Description nodes, first non-empty value per field wins.
    rating = 0
    title = description = label = ""
    keywords: list[str] = []
    creators: list[str] = []
    hierarchy: list[str] = []
    for desc in descs:
        rating = rating or _parse_rating(desc)
        title = title or _parse_alt_default(desc.find(f"{{{_NS['dc']}}}title"))
        description = description or _parse_alt_default(
            desc.find(f"{{{_NS['dc']}}}description"))
        keywords = keywords or _parse_bag(desc.find(f"{{{_NS['dc']}}}subject"))
        creators = creators or _parse_bag(desc.find(f"{{{_NS['dc']}}}creator"))
        label = label or _extract_label(desc)
        hierarchy = hierarchy or _parse_bag(desc.find(_LR_HIERARCHY))

    return XmpData(
        rating=rating,
        title=title,
        description=description,
        keywords=keywords,
        color_label=label,
        creator=creators[0] if creators else "",
        hierarchical_keywords=hierarchy,
    )
