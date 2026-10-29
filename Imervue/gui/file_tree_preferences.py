"""Validated sort preferences shared by the file tree's controls and proxy."""
from dataclasses import asdict, dataclass
import os

from Imervue.gui.file_tree_sort import normalize_sort_key
from Imervue.user_settings.user_setting_dict import user_setting_dict
from Imervue.user_settings import user_setting_dict as settings_store


def root_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)) if path else ""


@dataclass(frozen=True)
class TreeSortSettings:
    key: str = "name"
    ascending: bool = True
    folders_first: bool = True

    @classmethod
    def from_dict(cls, value):
        value = value if isinstance(value, dict) else {}
        return cls(normalize_sort_key(value.get("key")),
                   value.get("ascending", True) is not False,
                   value.get("folders_first", True) is not False)


def folder_overrides() -> dict:
    value = user_setting_dict.get("tree_folder_sort_overrides", {})
    return value if isinstance(value, dict) else {}


def sort_settings(path: str) -> TreeSortSettings:
    override = folder_overrides().get(root_key(path)) if path else None
    if isinstance(override, dict):
        return TreeSortSettings.from_dict(override)
    return TreeSortSettings.from_dict({
        "key": user_setting_dict.get("tree_sort_by", "name"),
        "ascending": user_setting_dict.get("tree_sort_ascending", True),
        "folders_first": user_setting_dict.get("tree_sort_folders_first", True),
    })


def save_sort_settings(path: str, settings: TreeSortSettings) -> None:
    key = root_key(path)
    if key and key in folder_overrides():
        user_setting_dict["tree_folder_sort_overrides"] = {
            **folder_overrides(), key: asdict(settings),
        }
    else:
        user_setting_dict.update(tree_sort_by=settings.key,
                                 tree_sort_ascending=settings.ascending,
                                 tree_sort_folders_first=settings.folders_first)
    settings_store.schedule_save()


def set_folder_override(path: str, settings: TreeSortSettings | None) -> None:
    key = root_key(path)
    if not key:
        return
    overrides = dict(folder_overrides())
    if settings is None:
        overrides.pop(key, None)
    else:
        overrides[key] = asdict(settings)
    user_setting_dict["tree_folder_sort_overrides"] = overrides
    settings_store.schedule_save()
