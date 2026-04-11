"""Recent folders / images tracking — configurable cap via user_setting_dict['max_recent']."""

DEFAULT_MAX_RECENT = 10
# Kept as a module-level constant for backwards compatibility (tests import it).
# Runtime code should call _max_recent() to honour the user's override.
MAX_RECENT = DEFAULT_MAX_RECENT


def _max_recent() -> int:
    """Read the configured recent-list cap, falling back to the default if unset/invalid."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    val = user_setting_dict.get("max_recent", DEFAULT_MAX_RECENT)
    try:
        n = int(val)
    except (TypeError, ValueError):
        return DEFAULT_MAX_RECENT
    # 下限 1（不能設成 0 讓清單完全停用，那等於關掉功能）；上限 200 避免使用者打字打錯。
    return max(1, min(200, n))


def set_max_recent(n: int) -> None:
    """Update the user-facing cap and persist it."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save
    user_setting_dict["max_recent"] = max(1, min(200, int(n)))
    # Trim existing lists down to the new cap immediately so the UI reflects the change.
    cap = _max_recent()
    for key in ("user_recent_folders", "user_recent_images"):
        lst = user_setting_dict.get(key, [])
        if len(lst) > cap:
            user_setting_dict[key] = lst[:cap]
    schedule_save()


def add_recent_folder(path: str):
    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save

    recent = user_setting_dict.get("user_recent_folders", [])

    if path in recent:
        recent.remove(path)

    recent.insert(0, path)
    user_setting_dict["user_recent_folders"] = recent[:_max_recent()]
    schedule_save()


def add_recent_image(path: str):
    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save

    recent = user_setting_dict.get("user_recent_images", [])

    if path in recent:
        recent.remove(path)

    recent.insert(0, path)
    user_setting_dict["user_recent_images"] = recent[:_max_recent()]
    schedule_save()


def clear_recent():
    from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save

    user_setting_dict["user_recent_folders"] = []
    user_setting_dict["user_recent_images"] = []
    schedule_save()
