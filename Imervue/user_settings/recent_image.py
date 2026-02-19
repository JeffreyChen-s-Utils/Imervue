MAX_RECENT = 10

def add_to_recent(path: str):
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    recent = user_setting_dict.get("user_recent_paths", [])

    if path in recent:
        recent.remove(path)

    recent.insert(0, path)

    if len(recent) > MAX_RECENT:
        recent = recent[:MAX_RECENT]

    user_setting_dict["user_recent_paths"] = recent

def add_recent_folder(path: str):
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    recent = user_setting_dict.get("user_recent_folders", [])

    if path in recent:
        recent.remove(path)

    recent.insert(0, path)
    user_setting_dict["user_recent_folders"] = recent[:MAX_RECENT]


def add_recent_image(path: str):
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    recent = user_setting_dict.get("user_recent_images", [])

    if path in recent:
        recent.remove(path)

    recent.insert(0, path)
    user_setting_dict["user_recent_images"] = recent[:MAX_RECENT]


def clear_recent():
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    user_setting_dict["user_recent_folders"] = []
    user_setting_dict["user_recent_images"] = []

