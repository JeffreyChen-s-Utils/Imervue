"""Export / import Smart Albums as a portable JSON document.

Round-trips each album's name + rules so a library's smart albums can be
backed up or shared between machines. The parsing core (:func:`parse_albums`)
is pure and validates the document without touching the DB; the file helpers
sit on top of :mod:`Imervue.library.smart_album` persistence.
"""
from __future__ import annotations

import json
from pathlib import Path

from Imervue.library import smart_album

_FORMAT_VERSION = 1
_ALBUMS_KEY = "albums"


def _serialize(albums: list[dict]) -> str:
    return json.dumps(
        {"version": _FORMAT_VERSION, _ALBUMS_KEY: albums},
        ensure_ascii=False, indent=2,
    )


def parse_albums(text: str) -> list[dict]:
    """Parse a JSON album document into validated ``{name, rules}`` entries.

    Malformed entries (missing name, non-dict rules) are skipped; a document
    that is not an object with an ``albums`` list raises ``ValueError``.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid album document: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("album document must be a JSON object")
    raw = data.get(_ALBUMS_KEY)
    if not isinstance(raw, list):
        raise ValueError("album document missing an 'albums' list")
    entries: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        rules = item.get("rules")
        if isinstance(name, str) and name and isinstance(rules, dict):
            entries.append({"name": name, "rules": rules})
    return entries


def export_albums(dest_path: str | Path) -> int:
    """Write every smart album to *dest_path* as JSON; returns the count."""
    albums = [
        {"name": a["name"], "rules": a["rules"]} for a in smart_album.list_all()
    ]
    Path(dest_path).write_text(_serialize(albums), encoding="utf-8")
    return len(albums)


def import_albums(src_path: str | Path, *, overwrite: bool = False) -> int:
    """Save smart albums from *src_path*; returns the number saved.

    Albums whose name already exists are skipped unless *overwrite* is set.
    """
    text = Path(src_path).read_text(encoding="utf-8")
    existing = {a["name"] for a in smart_album.list_all()}
    saved = 0
    for entry in parse_albums(text):
        if entry["name"] in existing and not overwrite:
            continue
        smart_album.save(entry["name"], entry["rules"])
        saved += 1
    return saved
