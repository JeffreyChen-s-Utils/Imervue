"""Tag & Album management — flexible image organization with custom tags and virtual albums."""

from __future__ import annotations


def get_all_tags() -> dict[str, list[str]]:
    """Return {tag_name: [image_path, ...]}."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return user_setting_dict.get("image_tags", {})


def get_tags_for_image(path: str) -> list[str]:
    """Return list of tag names attached to *path*."""
    tags = get_all_tags()
    return [name for name, paths in tags.items() if path in paths]


def add_tag(tag_name: str, path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    tags = user_setting_dict.setdefault("image_tags", {})
    paths = tags.setdefault(tag_name, [])
    if path in paths:
        return False
    paths.append(path)
    return True


def remove_tag(tag_name: str, path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    tags = user_setting_dict.setdefault("image_tags", {})
    paths = tags.get(tag_name, [])
    if path in paths:
        paths.remove(path)
        if not paths:
            tags.pop(tag_name, None)
        return True
    return False


def create_tag(tag_name: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    tags = user_setting_dict.setdefault("image_tags", {})
    if tag_name in tags:
        return False
    tags[tag_name] = []
    return True


def delete_tag(tag_name: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    tags = user_setting_dict.setdefault("image_tags", {})
    if tag_name in tags:
        del tags[tag_name]
        return True
    return False


def rename_tag(old_name: str, new_name: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    tags = user_setting_dict.setdefault("image_tags", {})
    if old_name not in tags or new_name in tags:
        return False
    tags[new_name] = tags.pop(old_name)
    return True


def get_all_albums() -> dict[str, list[str]]:
    """Return {album_name: [image_path, ...]}."""
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return user_setting_dict.get("albums", {})


def create_album(album_name: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    albums = user_setting_dict.setdefault("albums", {})
    if album_name in albums:
        return False
    albums[album_name] = []
    return True


def delete_album(album_name: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    albums = user_setting_dict.setdefault("albums", {})
    if album_name in albums:
        del albums[album_name]
        return True
    return False


def rename_album(old_name: str, new_name: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    albums = user_setting_dict.setdefault("albums", {})
    if old_name not in albums or new_name in albums:
        return False
    albums[new_name] = albums.pop(old_name)
    return True


def add_to_album(album_name: str, path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    albums = user_setting_dict.setdefault("albums", {})
    paths = albums.setdefault(album_name, [])
    if path in paths:
        return False
    paths.append(path)
    return True


def remove_from_album(album_name: str, path: str) -> bool:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    albums = user_setting_dict.setdefault("albums", {})
    paths = albums.get(album_name, [])
    if path in paths:
        paths.remove(path)
        return True
    return False


def get_album_images(album_name: str) -> list[str]:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    albums = user_setting_dict.get("albums", {})
    return list(albums.get(album_name, []))
