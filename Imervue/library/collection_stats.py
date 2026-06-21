"""Summarise a path collection's ratings, favourites, colour labels and culls.

A pure aggregation building block for a library / collection stats panel. The
core :func:`_summarize` works on plain mappings (no DB or settings access), so
it is trivially unit-testable; :func:`summarize` gathers the live data from
user settings, the colour-label store and the image index, then delegates.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from Imervue.library import image_index
from Imervue.user_settings.color_labels import COLORS, get_color_label
from Imervue.user_settings.user_setting_dict import user_setting_dict

_MAX_STARS = 5
_NONE_LABEL = "none"
_CULL_STATES = (
    image_index.CULL_PICK, image_index.CULL_REJECT, image_index.CULL_UNFLAGGED,
)


def summarize(paths: Iterable[str]) -> dict:
    """Aggregate rating / favourite / colour-label / cull stats for *paths*."""
    items = list(paths)
    ratings = user_setting_dict.get("image_ratings", {})
    favourites = user_setting_dict.get("image_favorites", [])
    labels = {path: get_color_label(path) for path in items}
    culls = {path: image_index.get_cull_state(path) for path in items}
    return _summarize(items, ratings, favourites, labels, culls)


def _summarize(
    paths: list[str],
    ratings: Mapping[str, int],
    favourites: Iterable[str],
    labels: Mapping[str, str | None],
    culls: Mapping[str, str],
) -> dict:
    """Pure aggregation over already-gathered per-path data."""
    fav_set = set(favourites) if isinstance(favourites, (list, set, tuple)) else set()
    distribution = dict.fromkeys(range(_MAX_STARS + 1), 0)
    for path in paths:
        distribution[_star_bucket(ratings.get(path, 0))] += 1
    rated = sum(distribution[star] for star in range(1, _MAX_STARS + 1))
    rating_sum = sum(star * distribution[star] for star in range(1, _MAX_STARS + 1))
    return {
        "total": len(paths),
        "rated": rated,
        "unrated": distribution[0],
        "average_rating": round(rating_sum / rated, 2) if rated else 0.0,
        "rating_distribution": distribution,
        "favorites": sum(1 for path in paths if path in fav_set),
        "color_labels": _count_labels(paths, labels),
        "cull": _count_culls(paths, culls),
    }


def _star_bucket(rating: object) -> int:
    """Clamp a stored rating into a 0-5 star bucket (out-of-range → unrated)."""
    value = int(rating)
    return value if 0 <= value <= _MAX_STARS else 0


def _count_labels(
    paths: list[str], labels: Mapping[str, str | None],
) -> dict[str, int]:
    counts = dict.fromkeys(COLORS, 0)
    counts[_NONE_LABEL] = 0
    for path in paths:
        label = labels.get(path)
        counts[label if label in counts else _NONE_LABEL] += 1
    return counts


def _count_culls(paths: list[str], culls: Mapping[str, str]) -> dict[str, int]:
    counts = dict.fromkeys(_CULL_STATES, 0)
    for path in paths:
        state = culls.get(path, image_index.CULL_UNFLAGGED)
        counts[state if state in counts else image_index.CULL_UNFLAGGED] += 1
    return counts
