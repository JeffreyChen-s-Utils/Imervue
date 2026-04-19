"""
Smart Albums — persist a filter query and reapply it later.

A rules dict supports these keys (all optional):
    - exts:              list[str]       file extensions without dot
    - min_width / min_height / min_size / max_size:  int
    - color_labels:      list[str]       colour names (see color_labels.COLORS)
    - min_rating:        int             1-5 (inclusive)
    - favorites_only:    bool
    - cull:              str             'pick' | 'reject' | 'unflagged'
    - tags_any / tags_all: list[str]     hierarchical tag paths
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
    return result


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
            paths = [p for p in paths if p in set(image_index.images_with_tag(t))]

    date_from = rules.get("date_from")
    date_to = rules.get("date_to")
    if date_from or date_to:
        paths = _apply_date_filter(paths, date_from, date_to)
    return paths


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
