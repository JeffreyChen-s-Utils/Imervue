"""
XMP sidecar read/write for Lightroom / Capture One interoperability.

An XMP sidecar is a ``<image>.xmp`` XML file stored next to the image that
holds ratings, keywords, titles, descriptions, and colour labels. Adobe
Camera Raw / Lightroom write one automatically; Capture One and most raw
developers can read them. Exchanging these lets Imervue round-trip
metadata with other editors without touching the image file itself.

Only four fields are round-tripped — the ones Imervue tracks and that map
cleanly to Adobe's XMP schema:

============  ============  =======================================
Imervue       XMP element   Notes
============  ============  =======================================
rating        xmp:Rating    integer 0\u20135 (0 = unrated, -1 = rejected)
title         dc:title      single language default entry
keywords      dc:subject    list of strings → ``image_tags``
color label   xmp:Label     free string; Imervue uses canonical names
============  ============  =======================================

All XML parsing goes through ``defusedxml`` to stay safe against XXE /
billion-laughs style attacks (SonarQube ``python:S2755``, bandit B405\u2013B411).
Writing uses ``xml.etree.ElementTree`` \u2014 that is safe because the tree is
built from typed Python values, not parsed untrusted input.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405  # nosec B405 - used for write only
from dataclasses import dataclass, field
from pathlib import Path

from defusedxml import ElementTree as DefusedET

# NOTE: the values below are XML *namespace identifiers*, not network URLs.
# XML namespaces (W3C REC-xml-names) are opaque strings that uniquely identify
# a vocabulary; by convention they look like http(s) URIs but are never
# dereferenced. The specific strings below are defined by the W3C and Adobe
# XMP specifications and MUST be reproduced verbatim for sidecars to be
# readable by Lightroom / Capture One. Flagging them as insecure HTTP is a
# false positive for SonarQube python:S5332 / bandit B113.
_NS = {
    "x": "adobe:ns:meta/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",  # NOSONAR
    "xmp": "http://ns.adobe.com/xap/1.0/",  # NOSONAR
    "dc": "http://purl.org/dc/elements/1.1/",  # NOSONAR
    "xml": "http://www.w3.org/XML/1998/namespace",  # NOSONAR
}
_RATING_MIN = -1
_RATING_MAX = 5
_XML_DECLARATION = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"


@dataclass
class XmpData:
    """In-memory representation of the subset of XMP Imervue cares about."""

    rating: int = 0
    title: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    color_label: str = ""

    def is_empty(self) -> bool:
        """Return True if every tracked field carries no information."""
        return (
            self.rating == 0
            and not self.title
            and not self.description
            and not self.keywords
            and not self.color_label
        )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def sidecar_path_for(image_path: str | Path) -> Path:
    """Return the canonical ``<image>.xmp`` path beside ``image_path``.

    Uses Adobe Bridge's convention of replacing the extension (``foo.jpg``
    \u2192 ``foo.xmp``) rather than appending. Simpler to find, simpler to
    clean up, and unambiguous for our primary targets (JPEG/PNG/TIFF).
    """
    return Path(image_path).with_suffix(".xmp")


def has_sidecar(image_path: str | Path) -> bool:
    """Return True if a sidecar exists for ``image_path``."""
    return sidecar_path_for(image_path).is_file()


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _find_description(root) -> object | None:
    """Locate ``rdf:Description`` regardless of whether the root is wrapped."""
    rdf_tag = f"{{{_NS['rdf']}}}Description"
    if root.tag == rdf_tag:
        return root
    for elem in root.iter(rdf_tag):
        return elem
    return None


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


def load(image_path: str | Path) -> XmpData:
    """Read the sidecar for ``image_path`` and return an ``XmpData``.

    Returns a default (empty) ``XmpData`` if the sidecar is missing or the
    XML is malformed \u2014 we never raise on bad user files, because losing the
    image view because of a broken sidecar would be a poor UX.
    """
    path = sidecar_path_for(image_path)
    if not path.is_file():
        return XmpData()
    try:
        tree = DefusedET.parse(str(path))
        root = tree.getroot()
    except (ET.ParseError, OSError):
        return XmpData()
    desc = _find_description(root)
    if desc is None:
        return XmpData()

    rating = _parse_rating(desc)
    title = _parse_alt_default(desc.find(f"{{{_NS['dc']}}}title"))
    description = _parse_alt_default(desc.find(f"{{{_NS['dc']}}}description"))
    keywords = _parse_bag(desc.find(f"{{{_NS['dc']}}}subject"))
    label = desc.get(f"{{{_NS['xmp']}}}Label") or ""
    if not label:
        child = desc.find(f"{{{_NS['xmp']}}}Label")
        label = (child.text or "").strip() if child is not None else ""

    return XmpData(
        rating=rating,
        title=title,
        description=description,
        keywords=keywords,
        color_label=label.strip(),
    )


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _make_alt(parent, tag: str, text: str) -> None:
    """Append ``dc:tag`` with an ``rdf:Alt/li[x-default]`` text child."""
    if not text:
        return
    field_el = ET.SubElement(parent, f"{{{_NS['dc']}}}{tag}")
    alt = ET.SubElement(field_el, f"{{{_NS['rdf']}}}Alt")
    li = ET.SubElement(alt, f"{{{_NS['rdf']}}}li")
    li.set(f"{{{_NS['xml']}}}lang", "x-default")
    li.text = text


def _make_bag(parent, tag: str, items: list[str]) -> None:
    """Append ``dc:tag`` with an ``rdf:Bag`` containing one ``li`` per item."""
    if not items:
        return
    field_el = ET.SubElement(parent, f"{{{_NS['dc']}}}{tag}")
    bag = ET.SubElement(field_el, f"{{{_NS['rdf']}}}Bag")
    for item in items:
        if not item:
            continue
        li = ET.SubElement(bag, f"{{{_NS['rdf']}}}li")
        li.text = item


def _build_tree(data: XmpData) -> ET.ElementTree:
    """Build an ``xmpmeta`` ElementTree from a ``XmpData`` value."""
    for prefix, uri in _NS.items():
        # Skip "xml" \u2014 it is reserved by the XML spec and already bound; if
        # we re-registered it with an empty prefix we would end up declaring
        # ``xmlns=""`` on the root which hides all default-namespaced children.
        if prefix == "xml":
            continue
        ET.register_namespace(prefix, uri)

    xmpmeta = ET.Element(f"{{{_NS['x']}}}xmpmeta")
    xmpmeta.set(f"{{{_NS['x']}}}xmptk", "Imervue XMP")
    rdf = ET.SubElement(xmpmeta, f"{{{_NS['rdf']}}}RDF")
    desc = ET.SubElement(rdf, f"{{{_NS['rdf']}}}Description")
    desc.set(f"{{{_NS['rdf']}}}about", "")

    if data.rating:
        desc.set(f"{{{_NS['xmp']}}}Rating", str(int(data.rating)))
    if data.color_label:
        desc.set(f"{{{_NS['xmp']}}}Label", data.color_label)
    _make_alt(desc, "title", data.title)
    _make_alt(desc, "description", data.description)
    _make_bag(desc, "subject", data.keywords)

    return ET.ElementTree(xmpmeta)


def save(image_path: str | Path, data: XmpData) -> Path:
    """Write the sidecar for ``image_path``. Empty data deletes the file.

    Returns the sidecar ``Path`` either way, so callers can report what was
    written.
    """
    path = sidecar_path_for(image_path)
    if data.is_empty():
        if path.is_file():
            path.unlink()
        return path

    tree = _build_tree(data)
    ET.indent(tree, space="  ")
    xml_bytes = ET.tostring(tree.getroot(), encoding="UTF-8")
    path.write_text(
        _XML_DECLARATION + xml_bytes.decode("utf-8"),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# High-level integration with user_setting_dict
# ---------------------------------------------------------------------------

def snapshot_from_settings(path: str) -> XmpData:
    """Build an ``XmpData`` from current Imervue settings for ``path``."""
    from Imervue.user_settings.color_labels import get_color_label
    from Imervue.user_settings.tags import get_tags_for_image
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    ratings = user_setting_dict.get("image_ratings") or {}
    try:
        rating = int(ratings.get(path, 0) or 0)
    except (TypeError, ValueError):
        rating = 0

    titles = user_setting_dict.get("image_titles") or {}
    descriptions = user_setting_dict.get("image_descriptions") or {}

    return XmpData(
        rating=rating,
        title=str(titles.get(path, "")),
        description=str(descriptions.get(path, "")),
        keywords=list(get_tags_for_image(path)),
        color_label=get_color_label(path) or "",
    )


def apply_to_settings(path: str, data: XmpData) -> None:
    """Write ``data`` back into Imervue settings for ``path``.

    Tags from the sidecar are merged into ``image_tags`` \u2014 we never delete
    tags the user already assigned just because the external editor didn't
    know about them.
    """
    from Imervue.user_settings.color_labels import set_color_label
    from Imervue.user_settings.tags import add_tag
    from Imervue.user_settings.user_setting_dict import (
        schedule_save, user_setting_dict,
    )

    ratings = user_setting_dict.setdefault("image_ratings", {})
    if data.rating:
        ratings[path] = int(data.rating)
    else:
        ratings.pop(path, None)

    if data.title:
        user_setting_dict.setdefault("image_titles", {})[path] = data.title
    else:
        user_setting_dict.get("image_titles", {}).pop(path, None)

    if data.description:
        user_setting_dict.setdefault("image_descriptions", {})[path] = data.description
    else:
        user_setting_dict.get("image_descriptions", {}).pop(path, None)

    for keyword in data.keywords:
        if keyword:
            add_tag(keyword, path)

    set_color_label(path, data.color_label or None)
    schedule_save()


def export_for(path: str) -> Path:
    """Snapshot settings for ``path`` and write the sidecar."""
    return save(path, snapshot_from_settings(path))


def import_for(path: str) -> XmpData:
    """Load the sidecar for ``path`` and merge it back into settings."""
    data = load(path)
    apply_to_settings(path, data)
    return data
