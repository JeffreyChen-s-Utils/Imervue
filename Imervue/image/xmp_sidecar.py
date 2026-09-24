"""
XMP sidecar read/write for cross-editor interoperability.

An XMP sidecar is an XML file stored next to the image that holds ratings,
keywords, titles, descriptions, and colour labels: ``<image>.xmp`` as Adobe
names it, or ``<image>.<ext>.xmp`` as darktable and digiKam do. Most
XMP-aware photo managers write one automatically and most raw developers
can read them. Exchanging these lets Imervue round-trip metadata with
other editors without touching the image file itself.

Only four fields are round-tripped — the ones Imervue tracks and that map
cleanly to Adobe's XMP schema:

============  ============  =======================================
Imervue       XMP element   Notes
============  ============  =======================================
rating        xmp:Rating    0\u20135; -1 = rejected, the library's cull reject
title         dc:title      single language default entry
keywords      dc:subject    list of strings → ``image_tags``
color label   xmp:Label     Lightroom's colour name or Bridge's word
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
from defusedxml.common import DefusedXmlException

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
_REJECTED = -1         # xmp:Rating of a rejected photo in Lightroom, Bridge and darktable
# Lightroom's (and darktable's) keyword hierarchy: a Bag of "Parent|Child|Leaf".
_LR_HIERARCHY = "{http://ns.adobe.com/lightroom/1.0/}hierarchicalSubject"  # NOSONAR
_EXIF_RATING = 0x4746          # 0-5 stars, written by Windows Explorer and some cameras
_EXIF_RATING_PERCENT = 0x4749  # the same as a 0-100 percentage
_XML_DECLARATION = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
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


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _existing_sidecar(image_path: str | Path) -> Path | None:
    """The sidecar beside *image_path*: ``foo.xmp``, else ``foo.jpg.xmp``; None without one."""
    image = Path(image_path)
    for candidate in (image.with_suffix(".xmp"), image.with_name(image.name + ".xmp")):
        if candidate.is_file():
            return candidate
    return None


def sidecar_path_for(image_path: str | Path) -> Path:
    """Return the sidecar path for ``image_path``: the existing one, else ``<image>.xmp``.

    Adobe's convention replaces the extension (``foo.jpg`` \u2192 ``foo.xmp``)
    and wins when both files exist; darktable and digiKam append it
    (``foo.jpg.xmp``), and that file is read and merged into when it is the
    only one. A new sidecar is written the Adobe way.
    """
    return _existing_sidecar(image_path) or Path(image_path).with_suffix(".xmp")


def has_sidecar(image_path: str | Path) -> bool:
    """Return True if a sidecar exists for ``image_path``."""
    return _existing_sidecar(image_path) is not None


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


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _find_descriptions(root) -> list:
    """All ``rdf:Description`` nodes, whether or not the root is wrapped.

    XMP legally splits properties across one ``Description`` per schema, so
    reading only the first node dropped fields written into later ones."""
    rdf_tag = f"{{{_NS['rdf']}}}Description"
    if root.tag == rdf_tag:
        return [root]
    return list(root.iter(rdf_tag))


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


def load(image_path: str | Path) -> XmpData:
    """Read the metadata for ``image_path`` and return an ``XmpData``.

    The sidecar when there is one; otherwise what the image file carries
    itself (:func:`load_embedded`) \u2014 Lightroom writes a JPEG's rating and
    keywords into the file rather than a sidecar, and so does Windows
    Explorer. Returns a default (empty) ``XmpData`` if there is nothing or
    the XML is malformed \u2014 we never raise on bad user files, because losing
    the image view because of a broken sidecar would be a poor UX.
    """
    path = _existing_sidecar(image_path)
    if path is None:
        return load_embedded(image_path)
    try:
        tree = DefusedET.parse(str(path))
        root = tree.getroot()
    except (ET.ParseError, OSError, DefusedXmlException):
        # DefusedXmlException covers a sidecar carrying a DTD / entity /
        # external reference (defusedxml rejects these to block XXE and
        # billion-laughs). It subclasses ValueError, so it slipped past the
        # old (ParseError, OSError) tuple and crashed keyword indexing /
        # smart-album evaluation instead of degrading to an empty sidecar.
        return XmpData()
    return _from_root(root)


def load_embedded(image_path: str | Path) -> XmpData:
    """The metadata the image file carries itself: its XMP packet, then its EXIF rating.

    The XMP packet is the one Pillow finds in a JPEG's APP1, a PNG's iTXt, a
    WebP chunk or TIFF tag 700. A photo rated in Windows Explorer or in camera
    may only have the EXIF ``Rating`` (0x4746) or ``RatingPercent`` (0x4749);
    that fills in the rating when the packet has none. Empty for a file
    Pillow can't open or one without either.
    """
    packet, exif_rating = _embedded_metadata(image_path)
    data = XmpData()
    if packet:
        try:
            data = _from_root(DefusedET.fromstring(packet))
        except (ET.ParseError, DefusedXmlException):
            data = XmpData()
    if not data.rating and exif_rating:
        data.rating = exif_rating
    return data


def _embedded_metadata(image_path: str | Path) -> tuple[bytes | None, int]:
    """``(XMP packet, EXIF stars)`` stored inside *image_path*; ``(None, 0)`` when unreadable."""
    from PIL import Image

    from Imervue.image.metadata_sync import percent_to_rating
    from Imervue.image.read_errors import IMAGE_READ_ERRORS
    try:
        with Image.open(image_path) as img:
            packet = img.info.get("xmp")
            exif = img.getexif()
    except IMAGE_READ_ERRORS:
        return None, 0
    if isinstance(packet, str):
        packet = packet.encode("utf-8")
    rating = exif.get(_EXIF_RATING)
    if rating is None and exif.get(_EXIF_RATING_PERCENT) is not None:
        rating = percent_to_rating(exif[_EXIF_RATING_PERCENT])
    try:
        stars = max(0, min(_RATING_MAX, int(rating or 0)))
    except (TypeError, ValueError):
        stars = 0
    return (packet if isinstance(packet, bytes) and packet.strip() else None), stars


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
    path.write_text(_XML_DECLARATION + xml_bytes.decode("utf-8"), encoding="utf-8")


def save(image_path: str | Path, data: XmpData) -> Path:
    """Write Imervue's fields into the sidecar for ``image_path``.

    An existing sidecar is merged into, not replaced: only rating, label,
    title, description, keywords and creator change, so what another editor
    wrote there (a raw developer's settings, crop, history, face regions)
    survives. The file is deleted only when nothing is left in it. Raises
    :class:`UnreadableSidecarError` (an ``OSError``) instead of overwriting a
    sidecar that can't be parsed. Returns the sidecar ``Path`` either way.
    """
    path = sidecar_path_for(image_path)
    tree = _existing_tree(path)
    if tree is None:
        if not data.is_empty():
            _write_tree(path, _build_tree(data))
        return path
    if _merge_into(tree, data) or not data.is_empty():
        _write_tree(path, tree)
    else:
        path.unlink()
    return path


# ---------------------------------------------------------------------------
# High-level integration with user_setting_dict
# ---------------------------------------------------------------------------

def snapshot_from_settings(path: str) -> XmpData:
    """Build an ``XmpData`` from current Imervue settings for ``path``.

    Imervue does not track ``dc:creator`` in its own settings, so the value is
    carried over from any existing sidecar. Without this, exporting settings
    would blank a creator an external editor (e.g. Lightroom) had written — and
    an otherwise-empty snapshot would delete a creator-only sidecar outright.
    The colour label is written as Lightroom names it unless the sidecar
    already words that colour its own way (see :func:`_label_to_write`). A
    photo culled as a reject is written ``xmp:Rating="-1"``, as Lightroom,
    Bridge and darktable mark a rejected photo.
    """
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
    existing = load(path)

    return XmpData(
        rating=_REJECTED if _is_rejected(path) else rating,
        title=str(titles.get(path, "")),
        description=str(descriptions.get(path, "")),
        keywords=list(get_tags_for_image(path)),
        color_label=_label_to_write(get_color_label(path), existing.color_label),
        creator=existing.creator,
    )


def apply_to_settings(path: str, data: XmpData) -> None:
    """Write ``data`` back into Imervue settings for ``path``.

    Tags from the sidecar are merged into ``image_tags`` \u2014 we never delete
    tags the user already assigned just because the external editor didn't
    know about them. The label becomes the colour it stands for
    (:func:`label_color`); one with no colour clears Imervue's. A rating of -1
    (rejected in Lightroom, Bridge and darktable) becomes the library's cull
    reject with no stars; any other rating lifts a reject Imervue had.
    """
    from Imervue.user_settings.color_labels import set_color_label
    from Imervue.user_settings.tags import add_tag
    from Imervue.user_settings.user_setting_dict import (
        schedule_save, user_setting_dict,
    )

    ratings = user_setting_dict.setdefault("image_ratings", {})
    if data.rating > 0:
        ratings[path] = int(data.rating)
    else:
        ratings.pop(path, None)
    _set_rejected(path, data.rating == _REJECTED)

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

    set_color_label(path, label_color(data.color_label))
    schedule_save()


def _is_rejected(path: str) -> bool:
    """Whether the library culls *path* as a reject; False without a library (none is created)."""
    from Imervue.library import image_index
    if not image_index.library_exists():
        return False
    return image_index.get_cull_state(path) == image_index.CULL_REJECT


def _set_rejected(path: str, rejected: bool) -> None:
    """Flag *path* a reject in the library, or lift a reject it has; other flags stay."""
    from Imervue.library import image_index
    if rejected:
        image_index.set_cull_state(path, image_index.CULL_REJECT)
    elif _is_rejected(path):
        image_index.set_cull_state(path, image_index.CULL_UNFLAGGED)


def export_for(path: str) -> Path:
    """Snapshot settings for ``path`` and write the sidecar."""
    return save(path, snapshot_from_settings(path))


def import_for(path: str) -> XmpData:
    """Load the sidecar for ``path`` and merge it back into settings."""
    data = load(path)
    apply_to_settings(path, data)
    return data
