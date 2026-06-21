"""
Smart Albums — persist a filter query and reapply it later.

A rules dict supports these keys (all optional):
    - exts:              list[str]       file extensions without dot
    - min_width / min_height / min_size / max_size:  int
    - min_aspect / max_aspect: float     width / height ratio bounds
    - color_labels:      list[str]       colour names (see color_labels.COLORS)
    - min_rating / max_rating: int       1-5 (inclusive)
    - favorites_only:    bool
    - cull:              str             'pick' | 'reject' | 'unflagged'
    - tags_any / tags_all: list[str]     hierarchical tag paths
    - tags_exclude:      list[str]       hierarchical tag paths to exclude
    - name_contains:     str
    - date_from / date_to: float         Unix timestamp, mtime
"""
from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path

from Imervue.library import image_index


def save(name: str, rules: dict) -> None:
    if not name:
        raise ValueError("album name required")
    image_index.save_smart_album(name, json.dumps(rules, ensure_ascii=False))


def delete(name: str) -> bool:
    return image_index.delete_smart_album(name)


def list_all() -> list[dict]:
    """Return [{name, rules, updated_at}]."""
    out: list[dict] = []
    for row in image_index.list_smart_albums():
        try:
            rules = json.loads(row["rules_json"])
        except (TypeError, ValueError):
            rules = {}
        out.append({
            "name": row["name"],
            "rules": rules,
            "updated_at": row["updated_at"] or 0.0,
        })
    return out


def get(name: str) -> dict | None:
    row = image_index.get_smart_album(name)
    if row is None:
        return None
    try:
        rules = json.loads(row["rules_json"])
    except (TypeError, ValueError):
        rules = {}
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
    result = _apply_user_setting_filters(result, rules)
    result = _apply_index_filters(result, rules)
    result = _apply_size_filters(result, rules)
    result = _apply_dimension_filters(result, rules)
    place = rules.get("place")
    if place:
        result = _apply_place_filter(result, place)
    missing = rules.get("missing")
    if missing:
        from Imervue.library.metadata_audit import paths_missing
        incomplete = set(paths_missing(result, missing))
        result = [p for p in result if p in incomplete]
    return result


def _apply_place_filter(paths: list[str], place: str) -> list[str]:
    """Keep paths whose GPS reverse-geocodes to the nearest-city *place*.

    Runs last (after the cheap filters narrow the set) because it extracts EXIF
    GPS per file. Untagged images can't match a place, so they drop out.
    """
    from Imervue.image.gps import extract_gps
    from Imervue.image.reverse_geocode import reverse_geocode
    out: list[str] = []
    for path in paths:
        coords = extract_gps(path)
        if coords is not None and reverse_geocode(coords[0], coords[1]) == place:
            out.append(path)
    return out


def auto_location_albums(
    path_coords: list[tuple[str, float, float]],
) -> list[tuple[str, dict]]:
    """Group ``(path, lat, lon)`` into one ``(album_name, rules)`` per city.

    Pure: the album name is the nearest-city place and its rule is a matching
    ``place`` filter. Returned sorted by name for stable output.
    """
    from Imervue.image.reverse_geocode import reverse_geocode
    buckets: dict[str, list[str]] = {}
    for path, lat, lon in path_coords:
        place = reverse_geocode(lat, lon)
        if place:
            buckets.setdefault(place, []).append(path)
    return [(place, {"place": place}) for place in sorted(buckets)]


def generate_location_albums(paths: Iterable[str]) -> int:
    """Create a smart album per nearest-city for the geotagged *paths*.

    Returns the number of albums created (one per distinct city found).
    """
    from Imervue.image.gps import collect_gps
    albums = auto_location_albums(collect_gps(list(paths)))
    for name, rules in albums:
        save(name, rules)
    return len(albums)


def _apply_user_setting_filters(paths: list[str], rules: dict) -> list[str]:
    from Imervue.user_settings.color_labels import filter_by_color
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    colors = rules.get("color_labels")
    if colors:
        keep: set[str] = set()
        for c in colors:
            keep.update(filter_by_color(paths, c))
        paths = [p for p in paths if p in keep]

    min_rating = rules.get("min_rating")
    if min_rating:
        ratings = user_setting_dict.get("image_ratings", {})
        paths = [p for p in paths if int(ratings.get(p, 0)) >= int(min_rating)]

    max_rating = rules.get("max_rating")
    if max_rating is not None:
        ratings = user_setting_dict.get("image_ratings", {})
        paths = [p for p in paths if int(ratings.get(p, 0)) <= int(max_rating)]

    if rules.get("favorites_only"):
        favs = user_setting_dict.get("image_favorites", [])
        fav_set = set(favs) if isinstance(favs, (list, set, tuple)) else set()
        paths = [p for p in paths if p in fav_set]
    return paths


def _apply_index_filters(paths: list[str], rules: dict) -> list[str]:
    cull = rules.get("cull")
    if cull:
        paths = image_index.filter_by_cull(paths, cull)

    tags_any = rules.get("tags_any") or []
    if tags_any:
        allowed: set[str] = set()
        for t in tags_any:
            allowed.update(image_index.images_with_tag(t))
        paths = [p for p in paths if p in allowed]

    tags_all = rules.get("tags_all") or []
    if tags_all:
        for t in tags_all:
            tagged = set(image_index.images_with_tag(t))
            paths = [p for p in paths if p in tagged]

    tags_exclude = rules.get("tags_exclude") or []
    if tags_exclude:
        excluded: set[str] = set()
        for t in tags_exclude:
            excluded.update(image_index.images_with_tag(t))
        paths = [p for p in paths if p not in excluded]

    date_from = rules.get("date_from")
    date_to = rules.get("date_to")
    if date_from or date_to:
        paths = _apply_date_filter(paths, date_from, date_to)
    return paths


def _apply_size_filters(paths: list[str], rules: dict) -> list[str]:
    """Filter by file size in bytes (``min_size`` / ``max_size``) via stat."""
    min_size = rules.get("min_size")
    max_size = rules.get("max_size")
    if not min_size and not max_size:
        return paths
    out: list[str] = []
    for p in paths:
        try:
            size = Path(p).stat().st_size
        except OSError:
            continue
        if min_size and size < int(min_size):
            continue
        if max_size and size > int(max_size):
            continue
        out.append(p)
    return out


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


def _apply_dimension_filters(paths: list[str], rules: dict) -> list[str]:
    """Filter by pixel dimensions (``min_width`` / ``min_height``) and aspect.

    Reads only the image header (no full decode) and runs after the cheaper
    filters, so it touches the smallest possible set. Unreadable images can't
    satisfy a dimension rule, so they're dropped.
    """
    min_w = rules.get("min_width")
    min_h = rules.get("min_height")
    min_aspect = rules.get("min_aspect")
    max_aspect = rules.get("max_aspect")
    if not any((min_w, min_h, min_aspect, max_aspect)):
        return paths
    from PIL import Image
    out: list[str] = []
    for p in paths:
        try:
            with Image.open(p) as im:
                width, height = im.size
        except OSError:
            continue
        if min_w and width < int(min_w):
            continue
        if min_h and height < int(min_h):
            continue
        if not _aspect_ok(width, height, min_aspect, max_aspect):
            continue
        out.append(p)
    return out


def _apply_date_filter(
    paths: list[str], date_from: float | None, date_to: float | None,
) -> list[str]:
    out: list[str] = []
    for p in paths:
        try:
            mtime = Path(p).stat().st_mtime
        except OSError:
            continue
        if date_from and mtime < float(date_from):
            continue
        if date_to and mtime > float(date_to):
            continue
        out.append(p)
    return out


def touch(name: str) -> None:
    """Bump the ``updated_at`` timestamp without changing the rules."""
    existing = get(name)
    if existing is None:
        return
    image_index.save_smart_album(name, json.dumps(existing["rules"]))
    _ = time.time()  # timestamp is set inside save_smart_album
