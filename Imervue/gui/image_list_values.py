"""Rating values, star geometry, and human-readable file sizes."""

from __future__ import annotations
import logging


logger = logging.getLogger("Imervue.gui.image_list_view")

_THUMB_SIZE = 48

LIST_MARK_ACTIONS = frozenset(
    {
        "rate_1",
        "rate_2",
        "rate_3",
        "rate_4",
        "rate_5",
        "favorite",
        "cull_pick",
        "cull_reject",
        "cull_unflag",
        "label_red",
        "label_yellow",
        "label_green",
        "label_blue",
        "label_purple",
    }
)

_MAX_THUMB_RETRIES = 2

_STAR_FILLED = "\u2605"

_STAR_EMPTY = "\u2606"

_RATING_MAX = 5


def _rating_for(path: str) -> int:
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    ratings = user_setting_dict.get("image_ratings") or {}
    try:
        return int(ratings.get(path, 0))
    except (TypeError, ValueError):
        return 0


def _format_rating(rating: int) -> str:
    if rating <= 0:
        return ""
    rating = min(max(int(rating), 0), _RATING_MAX)
    return _STAR_FILLED * rating + _STAR_EMPTY * (_RATING_MAX - rating)


def star_at(x: float, center_x: float, strip_width: float) -> int:
    """The star (1-5) under *x* in a strip of five stars *strip_width* wide centred on *center_x*.

    A click left or right of the strip counts as the nearest end star.
    """
    step = max(strip_width, 1.0) / _RATING_MAX
    left = center_x - step * _RATING_MAX / 2
    return min(max(int((x - left) // step) + 1, 1), _RATING_MAX)


def _fmt_size(kb: float) -> str:
    if kb >= 1024:
        return f"{kb / 1024:.2f} MB"
    return f"{kb:.1f} KB"
