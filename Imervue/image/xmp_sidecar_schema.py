"""XMP sidecar vocabulary: namespaces, the tracked fields and Imervue's managed properties.

Shared by the parsing, reading and writing halves of :mod:`Imervue.image.xmp_sidecar`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from Imervue.user_settings.color_labels import COLORS

# NOTE: the values below are XML *namespace identifiers*, not network URLs.
# XML namespaces (W3C REC-xml-names) are opaque strings that uniquely identify
# a vocabulary; by convention they look like http(s) URIs but are never
# dereferenced. The specific strings below are defined by the W3C and Adobe
# XMP specifications and MUST be reproduced verbatim for sidecars to be
# readable by other XMP-aware photo managers. Flagging them as insecure HTTP is a
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
# Lightroom's (and darktable's) keyword hierarchy: a Bag of "Parent|Child|Leaf".
_LR_HIERARCHY = "{http://ns.adobe.com/lightroom/1.0/}hierarchicalSubject"  # NOSONAR
# Adobe Bridge (and Lightroom's "Bridge Default" label set) labels with a
# workflow word per colour; Lightroom writes the colour's own name.
_BRIDGE_LABELS = {"select": "red", "second": "yellow", "approved": "green",
                  "review": "blue", "to do": "purple"}


@dataclass
class XmpData:
    """In-memory representation of the subset of XMP Imervue cares about."""

    rating: int = 0
    title: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    color_label: str = ""
    creator: str = ""
    # lr:hierarchicalSubject as written ("Places|Taiwan|Taipei"); read only,
    # a save leaves the file's own list alone.
    hierarchical_keywords: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True if every tracked field carries no information."""
        return (
            self.rating == 0
            and not self.title
            and not self.description
            and not self.keywords
            and not self.color_label
            and not self.creator
            and not self.hierarchical_keywords
        )


def label_color(label: str) -> str | None:
    """The Imervue colour an ``xmp:Label`` stands for, or None for a label it has no colour for.

    Lightroom writes the colour's name (``Red``), Bridge a workflow word
    (``Select`` = red, ``Second`` = yellow, ``Approved`` = green, ``Review`` =
    blue, ``To Do`` = purple); case is ignored.
    """
    text = label.strip().lower()
    return text if text in COLORS else _BRIDGE_LABELS.get(text)


def _label_to_write(color: str | None, existing: str) -> str:
    """The ``xmp:Label`` for Imervue's *color*, keeping the sidecar's *existing* word if it can.

    The same colour keeps its word (Bridge's ``Select`` stays); another
    colour is written as Lightroom names it (``Red``). With no colour in
    Imervue, a label it has no colour for (a custom one) is kept rather than
    wiped: Imervue never showed it, so it can't have been cleared there.
    """
    known = label_color(existing)
    if color is None:
        return existing if known is None else ""
    return existing if known == color else color.capitalize()


def _find_descriptions(root) -> list:
    """All ``rdf:Description`` nodes, whether or not the root is wrapped.

    XMP legally splits properties across one ``Description`` per schema, so
    reading only the first node dropped fields written into later ones."""
    rdf_tag = f"{{{_NS['rdf']}}}Description"
    if root.tag == rdf_tag:
        return [root]
    return list(root.iter(rdf_tag))


# The properties Imervue owns; everything else in a sidecar belongs to another
# editor (a raw developer's settings, crop, history, regions) and is kept.
_MANAGED = frozenset({
    f"{{{_NS['xmp']}}}Rating", f"{{{_NS['xmp']}}}Label",
    f"{{{_NS['dc']}}}title", f"{{{_NS['dc']}}}description",
    f"{{{_NS['dc']}}}subject", f"{{{_NS['dc']}}}creator",
})
_RDF_ABOUT = f"{{{_NS['rdf']}}}about"


def _strip_managed(descs: list) -> None:
    """Remove Imervue's properties, in attribute or element form, from every Description."""
    for desc in descs:
        for name in [key for key in desc.attrib if key in _MANAGED]:
            del desc.attrib[name]
        for child in [child for child in desc if child.tag in _MANAGED]:
            desc.remove(child)


def _holds_foreign_data(descs: list) -> bool:
    """Whether any Description still carries a property Imervue doesn't manage."""
    return any(len(desc) or any(key != _RDF_ABOUT for key in desc.attrib) for desc in descs)
