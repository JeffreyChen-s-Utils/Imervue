"""Smart Album rules backed by user settings and the library catalog.

Colour labels, ratings and favourites come from user settings; cull state,
tags and the mtime range go through the :mod:`Imervue.library.image_index`
facade, called as ``image_index.<name>`` so patches on the facade apply.
"""
from __future__ import annotations

from Imervue.library import image_index
from Imervue.library.smart_album_files import _apply_date_filter


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
        fav_set = set(favs) if isinstance(favs, list | set | tuple) else set()
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
