"""Bookmark / Collection management for cross-folder image collections."""

from __future__ import annotations

MAX_BOOKMARKS = 500


def get_bookmarks() -> list[str]:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return user_setting_dict.get("bookmarks", [])


def add_bookmark(path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    bookmarks = user_setting_dict.setdefault("bookmarks", [])
    if path in bookmarks:
        return False
    bookmarks.append(path)
    if len(bookmarks) > MAX_BOOKMARKS:
        bookmarks[:] = bookmarks[-MAX_BOOKMARKS:]
    return True


def remove_bookmark(path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    bookmarks = user_setting_dict.get("bookmarks", [])
    if path in bookmarks:
        bookmarks.remove(path)
        return True
    return False


def is_bookmarked(path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return path in user_setting_dict.get("bookmarks", [])


def clear_bookmarks():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict["bookmarks"] = []
