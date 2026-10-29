"""Per-image predicates behind the browse filter: tags, ratings, raw-query tokens.

Tags and ratings are read from the user settings at call time, so the
predicates always see the current library state.
"""
from __future__ import annotations

from Imervue.image.browser_state_index import ImageMeta


def _tag_matches(path: str, tag: str) -> bool:
    from Imervue.user_settings.tags import get_tags_for_image
    wanted = tag.strip().lower()
    return any(wanted in item.lower() for item in get_tags_for_image(path))


def _match_raw_query(path: str, query: str, meta: ImageMeta) -> bool:
    tokens = [part for part in (query or "").split() if part]
    return all(_token_matches(path, token, meta) for token in tokens)


def _token_matches(path: str, token: str, meta: ImageMeta) -> bool:
    if token.startswith("tag:"):
        return _tag_matches(path, token[4:])
    if token.startswith("rating:"):
        return _rating_matches(path, token[7:])
    if token.startswith("date:"):
        wanted = token[5:]
        return meta.mtime_date is not None and meta.mtime_date.isoformat().startswith(wanted)
    return token.lower() in meta.name


def _rating_matches(path: str, expr: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    try:
        rating = int((user_setting_dict.get("image_ratings") or {}).get(path, 0))
    except (TypeError, ValueError):
        rating = 0
    for op in (">=", "<=", ">", "<"):
        if expr.startswith(op):
            try:
                target = int(expr[len(op):])
            except ValueError:
                return True
            return {
                ">=": rating >= target,
                "<=": rating <= target,
                ">": rating > target,
                "<": rating < target,
            }[op]
    try:
        return rating == int(expr)
    except ValueError:
        return True

