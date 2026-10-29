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

This module is the public API and owns saving plus the settings integration;
the vocabulary, parsing, reading and writing live in the ``xmp_sidecar_*``
siblings and are re-exported here.
"""
from __future__ import annotations

from pathlib import Path

from Imervue.image.xmp_sidecar_read import (
    has_sidecar,
    load,
    load_embedded,
    sidecar_path_for,
)
from Imervue.image.xmp_sidecar_schema import (
    XmpData,
    _label_to_write,
    label_color,
)
from Imervue.image.xmp_sidecar_write import (
    UnreadableSidecarError,
    _build_tree,
    _existing_tree,
    _merge_into,
    _write_tree,
)

__all__ = [
    "XmpData",
    "UnreadableSidecarError",
    "sidecar_path_for",
    "has_sidecar",
    "label_color",
    "_label_to_write",
    "load",
    "load_embedded",
    "save",
    "snapshot_from_settings",
    "apply_to_settings",
    "export_for",
    "import_for",
]

_REJECTED = -1         # xmp:Rating of a rejected photo in Lightroom, Bridge and darktable


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

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
