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

from Imervue.image.video_frames import VIDEO_EXTENSIONS

_DIGITS = re.compile(r"(\d+)")
_TRUE = {"1", "true", "yes", "y", "on"}
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


def _apply_token(field: str, value: str, acc: dict, rules: dict) -> None:
    if field in _LIST_KEYS:
        acc[_LIST_KEYS[field]].append(value)
    elif field == "ext":
        acc["exts"].append(value.lstrip("."))
    elif field == "type" and value.lower() == "video":
        acc["exts"].extend(sorted(e.lstrip(".") for e in VIDEO_EXTENSIONS))
    elif field == "name":
        acc["free"].append(value)
    elif field == "place":
        rules["place"] = value
    elif field == "missing":
        rules.setdefault("missing", []).append(value.lower())
    elif field == "cull":
        rules["cull"] = value.lower()
    elif field == "rating":
        match = _DIGITS.search(value)
        if match:
            rules["min_rating"] = int(match.group(1))
    elif field in ("fav", "favorite", "favourite"):
        rules["favorites_only"] = value.lower() in _TRUE
