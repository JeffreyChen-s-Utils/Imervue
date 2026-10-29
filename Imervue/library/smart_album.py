"""
Smart Albums — persist a filter query and reapply it later.

A rules dict supports these keys (all optional):
    - exts:              list[str]       file extensions without dot
    - min_width / max_width / min_height / max_height:  int
    - min_size / max_size:  int
    - min_aspect / max_aspect: float     width / height ratio bounds
    - color_labels:      list[str]       colour names (see color_labels.COLORS)
    - min_rating / max_rating: int       1-5 (inclusive)
    - favorites_only:    bool
    - cull:              str             'pick' | 'reject' | 'unflagged'
    - tags_any / tags_all: list[str]     hierarchical tag paths
    - tags_exclude:      list[str]       hierarchical tag paths to exclude
    - name_contains:     str
    - name_regex:        str             regex matched against the filename
    - name_glob:         str             shell glob matched against the filename
    - camera:            str             substring matched against EXIF make/model
    - lens:              str             substring matched against EXIF lens model
    - date_from / date_to: float         Unix timestamp, mtime
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path

from Imervue.library import image_index
from Imervue.library.smart_album_catalog import (
    _apply_index_filters,
    _apply_user_setting_filters,
)
from Imervue.library.smart_album_dimensions import _apply_dimension_filters
from Imervue.library.smart_album_files import (
    _apply_exif_filters,
    _apply_name_pattern_filters,
    _apply_size_filters,
)
from Imervue.library.smart_album_location import (
    _apply_place_filter,
    auto_location_albums,
    place_matches,
)

__all__ = [
    "apply_to_paths",
    "auto_location_albums",
    "delete",
    "generate_location_albums",
    "get",
    "list_all",
    "place_matches",
    "save",
    "touch",
]


def save(name: str, rules: dict) -> None:
    if not name:
        raise ValueError("album name required")
    image_index.save_smart_album(name, json.dumps(rules, ensure_ascii=False))


def delete(name: str) -> bool:
    return image_index.delete_smart_album(name)


def _decode_rules(rules_json) -> dict:
    """Decode a stored ``rules_json``; anything unreadable is the empty rule set."""
    try:
        return json.loads(rules_json)
    except (TypeError, ValueError):
        return {}


def list_all() -> list[dict]:
    """Return [{name, rules, updated_at}]."""
    return [
        {
            "name": row["name"],
            "rules": _decode_rules(row["rules_json"]),
            "updated_at": row["updated_at"] or 0.0,
        }
        for row in image_index.list_smart_albums()
    ]


def get(name: str) -> dict | None:
    row = image_index.get_smart_album(name)
    if row is None:
        return None
    rules = _decode_rules(row["rules_json"])
    return {"name": row["name"], "rules": rules, "updated_at": row["updated_at"]}


def apply_to_paths(paths: Iterable[str], rules: dict) -> list[str]:
    """Filter a path list in-memory by the rules dict (no DB round-trip needed)."""
    result = list(paths)
    exts = rules.get("exts")
    if exts:
        ext_set = {e.lower().lstrip(".") for e in exts}
        result = [p for p in result if Path(p).suffix.lower().lstrip(".") in ext_set]
    name_contains = rules.get("name_contains")
    if name_contains:
        q = name_contains.lower()
        result = [p for p in result if q in Path(p).name.lower()]
    result = _apply_name_pattern_filters(result, rules)
    result = _apply_user_setting_filters(result, rules)
    result = _apply_index_filters(result, rules)
    result = _apply_size_filters(result, rules)
    result = _apply_dimension_filters(result, rules)
    place = rules.get("place")
    if place:
        result = _apply_place_filter(result, place)
    result = _apply_exif_filters(result, rules)
    missing = rules.get("missing")
    if missing:
        from Imervue.library.metadata_audit import paths_missing
        incomplete = set(paths_missing(result, missing))
        result = [p for p in result if p in incomplete]
    return result


def generate_location_albums(paths: Iterable[str]) -> int:
    """Create a smart album per nearest-city for the geotagged *paths*.

    Returns the number of albums created (one per distinct city found).
    """
    from Imervue.image.gps import collect_gps
    albums = auto_location_albums(collect_gps(list(paths)))
    for name, rules in albums:
        save(name, rules)
    return len(albums)


def touch(name: str) -> None:
    """Bump the ``updated_at`` timestamp without changing the rules."""
    existing = get(name)
    if existing is None:
        return
    image_index.save_smart_album(name, json.dumps(existing["rules"]))
    _ = time.time()  # timestamp is set inside save_smart_album
