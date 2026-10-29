"""Serialise :class:`XmpData` as a new sidecar, or merge it into an existing one.

Writing uses ``xml.etree.ElementTree`` \u2014 that is safe because the tree is
built from typed Python values, not parsed untrusted input; an existing sidecar
is parsed through ``defusedxml``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET  # noqa: S405  # nosec B405 - used for write only
from pathlib import Path

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

from Imervue.image.xmp_sidecar_schema import (
    _NS,
    _RDF_ABOUT,
    XmpData,
    _find_descriptions,
    _holds_foreign_data,
    _strip_managed,
)
from Imervue.system.atomic_write import write_text_atomically

_XML_DECLARATION = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"


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


def _make_seq(parent, tag: str, items: list[str]) -> None:
    """Append ``dc:tag`` with an ordered ``rdf:Seq`` of ``li`` entries."""
    entries = [item for item in items if item]
    if not entries:
        return
    field_el = ET.SubElement(parent, f"{{{_NS['dc']}}}{tag}")
    seq = ET.SubElement(field_el, f"{{{_NS['rdf']}}}Seq")
    for item in entries:
        li = ET.SubElement(seq, f"{{{_NS['rdf']}}}li")
        li.text = item


class UnreadableSidecarError(OSError):
    """An existing sidecar can't be parsed, so it is left alone rather than overwritten."""


def _register_namespaces(extra: dict[str, str] | None = None) -> None:
    """Bind the prefixes the written XML uses: Imervue's own plus a parsed file's."""
    for prefix, uri in {**_NS, **(extra or {})}.items():
        # Skip "xml" — it is reserved by the XML spec and already bound; if
        # we re-registered it with an empty prefix we would end up declaring
        # ``xmlns=""`` on the root which hides all default-namespaced children.
        if prefix in ("xml", ""):
            continue
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:   # a prefix ElementTree reserves (ns0, ns1, ...)
            continue


def _write_fields(desc, data: XmpData) -> None:
    """Put *data*'s non-empty fields onto the ``rdf:Description`` *desc*."""
    if data.rating:
        desc.set(f"{{{_NS['xmp']}}}Rating", str(int(data.rating)))
    if data.color_label:
        desc.set(f"{{{_NS['xmp']}}}Label", data.color_label)
    _make_alt(desc, "title", data.title)
    _make_alt(desc, "description", data.description)
    _make_bag(desc, "subject", data.keywords)
    _make_seq(desc, "creator", [data.creator])


def _build_tree(data: XmpData) -> ET.ElementTree:
    """Build an ``xmpmeta`` ElementTree from a ``XmpData`` value."""
    _register_namespaces()
    xmpmeta = ET.Element(f"{{{_NS['x']}}}xmpmeta")
    xmpmeta.set(f"{{{_NS['x']}}}xmptk", "Imervue XMP")
    rdf = ET.SubElement(xmpmeta, f"{{{_NS['rdf']}}}RDF")
    desc = ET.SubElement(rdf, f"{{{_NS['rdf']}}}Description")
    desc.set(f"{{{_NS['rdf']}}}about", "")
    _write_fields(desc, data)
    return ET.ElementTree(xmpmeta)


def _existing_tree(path: Path) -> ET.ElementTree | None:
    """The parsed sidecar at *path* with its namespace prefixes registered; None if absent."""
    if not path.is_file():
        return None
    try:
        prefixes = {prefix: uri for _event, (prefix, uri)
                    in DefusedET.iterparse(str(path), events=("start-ns",))}
        tree = DefusedET.parse(str(path))
    except (ET.ParseError, DefusedXmlException) as exc:
        raise UnreadableSidecarError(f"{path} is not readable XMP; leaving it as it is") from exc
    _register_namespaces(prefixes)
    return tree


def _merge_into(tree: ET.ElementTree, data: XmpData) -> bool:
    """Swap Imervue's properties in *tree* for *data*'s; False when nothing is left in it."""
    root = tree.getroot()
    descs = _find_descriptions(root)
    _strip_managed(descs)
    foreign = _holds_foreign_data(descs)
    if not descs:
        rdf = root.find(f"{{{_NS['rdf']}}}RDF")
        if rdf is None:
            rdf = ET.SubElement(root, f"{{{_NS['rdf']}}}RDF")
        desc = ET.SubElement(rdf, f"{{{_NS['rdf']}}}Description")
        desc.set(_RDF_ABOUT, "")
        descs = [desc]
    _write_fields(descs[0], data)
    return foreign


def _write_tree(path: Path, tree: ET.ElementTree) -> None:
    ET.indent(tree, space="  ")
    xml_bytes = ET.tostring(tree.getroot(), encoding="UTF-8")
    # In one step: the file may hold a raw developer's edits, and a write cut
    # short (full disk, crash) would leave it unreadable, those edits with it.
    write_text_atomically(path, _XML_DECLARATION + xml_bytes.decode("utf-8"))
