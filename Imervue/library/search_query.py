"""Parse a free-text search query into Smart Album rules.

A compact query language maps onto the existing ``smart_album`` rule dict, so a
typed query reuses the whole filter pipeline (and tag index, ratings, colours,
place lookup) with no new evaluation code:

    kw:beach tag:trip rating:>=4 color:red type:video name:sunset place:"Paris"
    fav:true cull:pick ext:png

Pure: ``parse_query`` turns a string into a rules dict; tests round-trip query →
rules. The dialog just feeds the result to ``smart_album.apply_to_paths``.
"""
from __future__ import annotations

import re
import time

from Imervue.image.video_frames import VIDEO_EXTENSIONS

_DIGITS = re.compile(r"(\d+)")
_FLOAT = re.compile(r"(\d+(?:\.\d+)?)")
_TRUE = {"1", "true", "yes", "y", "on"}
_SECONDS_PER_DAY = 86400.0
_SIZE_UNITS = {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}
_LIST_KEYS = {
    "kw": "tags", "keyword": "tags", "tag": "tags", "tags": "tags",
    "color": "colors", "colour": "colors",
}
# Keys that name a tag, so ``-tag:foo`` / ``-kw:foo`` can exclude one.
_TAG_KEYS = {key for key, mapped in _LIST_KEYS.items() if mapped == "tags"}


def _is_tag_negation(token: str) -> bool:
    """True for a ``-tag:foo`` style token that excludes a tag."""
    if not token.startswith("-") or ":" not in token:
        return False
    field, _, value = token[1:].partition(":")
    return field.lower().strip() in _TAG_KEYS and bool(value.strip())


def parse_query(query: str) -> dict:
    """Parse *query* into a ``smart_album`` rules dict."""
    acc: dict[str, list[str]] = {
        "tags": [], "tags_exclude": [], "colors": [], "exts": [], "free": [],
    }
    rules: dict = {}
    for token in query.split():
        if _is_tag_negation(token):
            acc["tags_exclude"].append(token[1:].partition(":")[2].strip())
            continue
        field, sep, value = token.partition(":")
        value = value.strip()
        if not sep or not value:
            acc["free"].append(token)
            continue
        _apply_token(field.lower().strip(), value, acc, rules)
    if acc["tags"]:
        rules["tags_all"] = acc["tags"]
    if acc["tags_exclude"]:
        rules["tags_exclude"] = acc["tags_exclude"]
    if acc["colors"]:
        rules["color_labels"] = acc["colors"]
    if acc["exts"]:
        rules["exts"] = acc["exts"]
    if acc["free"]:
        rules["name_contains"] = " ".join(acc["free"])
    return rules


def _apply_ext(value: str, acc: dict, _rules: dict) -> None:
    acc["exts"].append(value.lstrip("."))


def _apply_type(value: str, acc: dict, _rules: dict) -> None:
    if value.lower() == "video":
        acc["exts"].extend(sorted(e.lstrip(".") for e in VIDEO_EXTENSIONS))


def _apply_name(value: str, acc: dict, _rules: dict) -> None:
    acc["free"].append(value)


def _apply_place(value: str, _acc: dict, rules: dict) -> None:
    rules["place"] = value


def _apply_missing(value: str, _acc: dict, rules: dict) -> None:
    rules.setdefault("missing", []).append(value.lower())


def _apply_cull(value: str, _acc: dict, rules: dict) -> None:
    rules["cull"] = value.lower()


def _apply_fav(value: str, _acc: dict, rules: dict) -> None:
    rules["favorites_only"] = value.lower() in _TRUE


def _apply_rating(value: str, _acc: dict, rules: dict) -> None:
    """``rating:>=4`` / ``rating:3`` set a floor; ``rating:<=3`` sets a ceiling."""
    match = _DIGITS.search(value)
    if match is None:
        return
    rules["max_rating" if "<" in value else "min_rating"] = int(match.group(1))


def _apply_aspect(value: str, _acc: dict, rules: dict) -> None:
    """``aspect:>1.5`` keeps wide images; ``aspect:<1`` keeps tall ones."""
    match = _FLOAT.search(value)
    if match is None:
        return
    rules["max_aspect" if "<" in value else "min_aspect"] = float(match.group(1))


def _apply_age(value: str, _acc: dict, rules: dict) -> None:
    """``age:<30d`` keeps files modified in the last N days; ``age:>30d`` older.

    Resolved to an absolute mtime cutoff at parse time, reusing the
    ``date_from`` / ``date_to`` evaluation.
    """
    match = _FLOAT.search(value)
    if match is None:
        return
    cutoff = time.time() - float(match.group(1)) * _SECONDS_PER_DAY
    rules["date_from" if "<" in value else "date_to"] = cutoff


def _set_int_range(value: str, rules: dict, min_key: str, max_key: str) -> None:
    """``<N`` sets *max_key*, otherwise *min_key*, from the integer in *value*."""
    match = _DIGITS.search(value)
    if match is None:
        return
    rules[max_key if "<" in value else min_key] = int(match.group(1))


def _apply_width(value: str, _acc: dict, rules: dict) -> None:
    """``width:>1920`` / ``width:<800`` bound the pixel width."""
    _set_int_range(value, rules, "min_width", "max_width")


def _apply_height(value: str, _acc: dict, rules: dict) -> None:
    """``height:>1080`` / ``height:<600`` bound the pixel height."""
    _set_int_range(value, rules, "min_height", "max_height")


def _parse_size_bytes(value: str) -> int | None:
    """Parse ``500kb`` / ``1.5mb`` / ``2048`` into bytes; None if unrecognised."""
    match = _FLOAT.search(value)
    if match is None:
        return None
    unit = value[match.end():].strip().lower()
    if unit and unit not in _SIZE_UNITS:
        return None
    return int(float(match.group(1)) * _SIZE_UNITS.get(unit, 1))


def _apply_size(value: str, _acc: dict, rules: dict) -> None:
    """``size:>1mb`` sets a floor, ``size:<500kb`` a ceiling (kb/mb/gb units)."""
    size = _parse_size_bytes(value)
    if size is None:
        return
    rules["max_size" if "<" in value else "min_size"] = size


def _apply_regex(value: str, _acc: dict, rules: dict) -> None:
    """``re:IMG_\\d+`` matches the filename against a regular expression."""
    rules["name_regex"] = value


def _apply_glob(value: str, _acc: dict, rules: dict) -> None:
    """``glob:*.png`` matches the filename against a shell glob pattern."""
    rules["name_glob"] = value


_FIELD_HANDLERS = {
    "ext": _apply_ext,
    "type": _apply_type,
    "name": _apply_name,
    "place": _apply_place,
    "missing": _apply_missing,
    "cull": _apply_cull,
    "rating": _apply_rating,
    "fav": _apply_fav,
    "favorite": _apply_fav,
    "favourite": _apply_fav,
    "aspect": _apply_aspect,
    "age": _apply_age,
    "size": _apply_size,
    "width": _apply_width,
    "height": _apply_height,
    "re": _apply_regex,
    "regex": _apply_regex,
    "glob": _apply_glob,
}


def _apply_token(field: str, value: str, acc: dict, rules: dict) -> None:
    if field in _LIST_KEYS:
        acc[_LIST_KEYS[field]].append(value)
        return
    handler = _FIELD_HANDLERS.get(field)
    if handler is not None:
        handler(value, acc, rules)
