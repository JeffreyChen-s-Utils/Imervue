"""Bookmark / Collection management for cross-folder image collections."""

from __future__ import annotations

MAX_BOOKMARKS = 5000

# ---------------------------------------------------------------------------
# Fast-lookup set cache
# ---------------------------------------------------------------------------
# The source of truth is the list stored in user_setting_dict["bookmarks"] so
# we can JSON-serialize it. But `path in list` is O(n), and is_bookmarked() is
# called from hot paths (tile grid overlays, right-click menus) — O(n) × 5000
# bookmarks is visibly slow. We keep a parallel set as a read cache and
# invalidate it via id() whenever the underlying list is replaced (e.g. when
# read_user_setting() loads from disk).

_bookmark_set: set[str] = set()
_cached_list_id: int = 0


def _ensure_set_synced() -> set[str]:
    """Return the membership set, rebuilding it if the backing list was swapped out."""
    global _bookmark_set, _cached_list_id
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    lst = user_setting_dict.get("bookmarks")
    if lst is None:
        _bookmark_set = set()
        _cached_list_id = 0
        return _bookmark_set
    if id(lst) != _cached_list_id:
        _bookmark_set = set(lst)
        _cached_list_id = id(lst)
    return _bookmark_set


def get_bookmarks() -> list[str]:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return user_setting_dict.get("bookmarks", [])


def add_bookmark(path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save
    bookmark_set = _ensure_set_synced()
    if path in bookmark_set:
        return False
    bookmarks = user_setting_dict.setdefault("bookmarks", [])
    # setdefault may have created a new list; re-sync the id cache.
    global _cached_list_id
    if id(bookmarks) != _cached_list_id:
        bookmark_set = _ensure_set_synced()
    bookmarks.append(path)
    bookmark_set.add(path)
    if len(bookmarks) > MAX_BOOKMARKS:
        dropped = bookmarks[:-MAX_BOOKMARKS]
        bookmarks[:] = bookmarks[-MAX_BOOKMARKS:]
        bookmark_set.difference_update(dropped)
    schedule_save()
    return True


def remove_bookmark(path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save
    bookmark_set = _ensure_set_synced()
    if path not in bookmark_set:
        return False
    bookmarks = user_setting_dict.get("bookmarks", [])
    try:
        bookmarks.remove(path)
    except ValueError:
        # Set claimed membership but list disagreed — resync and bail.
        bookmark_set.discard(path)
        return False
    bookmark_set.discard(path)
    schedule_save()
    return True


def is_bookmarked(path: str) -> bool:
    return path in _ensure_set_synced()


def clear_bookmarks():
    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save
    global _bookmark_set, _cached_list_id
    user_setting_dict["bookmarks"] = []
    _bookmark_set = set()
    _cached_list_id = id(user_setting_dict["bookmarks"])
    schedule_save()
