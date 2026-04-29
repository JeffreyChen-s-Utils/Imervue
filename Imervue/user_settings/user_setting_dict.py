import json
import logging
import os
import threading
from pathlib import Path
from threading import Lock
from typing import Any

from Imervue.system.app_paths import user_settings_path as _user_settings_path

# 使用者設定的全域字典
# Global dictionary for user settings — always reflects the *current* profile.
user_setting_dict: dict[str, Any] = {
    "language": "English",
    "user_recent_folders": [],
    "user_recent_images": [],
    "user_last_folder": "",
    "bookmarks": [],
}

# 多帳號設定 — 預設只有 "default" 一個 profile.
# Sidecar state tracking which profile is active and which exist on disk.
# Lives outside ``user_setting_dict`` so that profile switching can mutate
# the dict freely without trampling the meta info.
DEFAULT_PROFILE = "default"
_profile_state: dict[str, Any] = {
    "current": DEFAULT_PROFILE,
    "available": [DEFAULT_PROFILE],
}

_lock = Lock()

# ---------------------------------------------------------------------------
# Debounced background save
# ---------------------------------------------------------------------------
# 任何一次設定變動都應該呼叫 schedule_save()。它會把真正的寫入延後 _SAVE_DEBOUNCE_SEC
# 秒，期間若再被呼叫就重置計時，避免高頻變動（評分、收藏、拖曳選取）瘋狂寫檔。
# 真正落地時會用 atomic write（tmp + os.replace），避免寫到一半斷電留下殘缺 JSON。

_SAVE_DEBOUNCE_SEC = 2.0
_save_timer: threading.Timer | None = None
_save_timer_lock = threading.Lock()
_settings_logger = logging.getLogger("Imervue.settings")


def schedule_save() -> None:
    """Debounced async save — persist user settings a few seconds after the last mutation."""
    global _save_timer
    with _save_timer_lock:
        if _save_timer is not None:
            _save_timer.cancel()
        t = threading.Timer(_SAVE_DEBOUNCE_SEC, _flush_save)
        t.daemon = True
        _save_timer = t
        t.start()


def cancel_pending_save() -> None:
    """Cancel any pending debounced save — call before an immediate flush on shutdown."""
    global _save_timer
    with _save_timer_lock:
        if _save_timer is not None:
            _save_timer.cancel()
            _save_timer = None


def _flush_save() -> None:
    try:
        write_user_setting()
    except Exception as e:
        _settings_logger.error(f"Debounced save failed: {e}")


# ---------------------------------------------------------------------------
# Profile-aware persistence
# ---------------------------------------------------------------------------
# On-disk format (v2 — multi-profile):
#   {
#       "current_profile": "default",
#       "profiles": {
#           "default": {"language": "English", ...},
#           "client_a": {"language": "English", ...}
#       }
#   }
#
# Legacy format (v1 — single profile):
#   {"language": "English", "user_recent_folders": [], ...}
#
# ``read_user_setting`` transparently migrates v1 → v2 by treating the entire
# legacy payload as the "default" profile. ``write_user_setting`` always emits
# v2.


def write_user_setting() -> Path:
    """
    將使用者設定寫入 JSON 檔案（多帳號格式）。
    Write user settings to disk in the multi-profile container.

    Other profiles' data is preserved by reading the existing file first
    and merging — the in-memory ``user_setting_dict`` only holds the
    currently-active profile, so we can never overwrite an inactive one.
    """
    user_setting_file = _user_settings_path()
    existing_profiles = _read_existing_profiles(user_setting_file)
    current = current_profile()
    existing_profiles[current] = dict(user_setting_dict)
    payload = {
        "current_profile": current,
        "profiles": existing_profiles,
    }
    write_json(str(user_setting_file), payload)
    return user_setting_file


def read_user_setting() -> Path:
    """
    讀取使用者設定檔，並更新全域字典（含 v1→v2 自動遷移）。
    Read settings JSON, populate the global dict for the active profile.
    """
    user_setting_file = _user_settings_path()
    if not (user_setting_file.exists() and user_setting_file.is_file()):
        return user_setting_file
    data = read_json(str(user_setting_file))
    if not isinstance(data, dict):
        return user_setting_file

    if _looks_like_multi_profile(data):
        _load_multi_profile(data)
    else:
        _load_legacy_profile(data)
    return user_setting_file


def _looks_like_multi_profile(data: dict) -> bool:
    return (
        "profiles" in data
        and isinstance(data.get("profiles"), dict)
        and "current_profile" in data
    )


def _load_multi_profile(data: dict) -> None:
    profiles = {
        name: payload for name, payload in data["profiles"].items()
        if isinstance(payload, dict)
    }
    if not profiles:
        profiles = {DEFAULT_PROFILE: {}}
    current = str(data.get("current_profile", DEFAULT_PROFILE))
    if current not in profiles:
        current = next(iter(profiles))
    _profile_state["current"] = current
    _profile_state["available"] = list(profiles.keys())
    user_setting_dict.update(profiles[current])


def _load_legacy_profile(data: dict) -> None:
    """Treat a v1 single-profile JSON file as the 'default' profile."""
    user_setting_dict.update(data)
    _profile_state["current"] = DEFAULT_PROFILE
    _profile_state["available"] = [DEFAULT_PROFILE]


def _read_existing_profiles(path: Path) -> dict[str, dict]:
    """Return the on-disk profile map, or an empty dict if file is absent / invalid."""
    if not path.exists():
        return {}
    loaded = read_json(str(path))
    if not isinstance(loaded, dict):
        return {}
    if not _looks_like_multi_profile(loaded):
        # Migrate legacy file — wrap its contents under "default".
        return {DEFAULT_PROFILE: dict(loaded)}
    return {
        name: dict(payload) for name, payload in loaded["profiles"].items()
        if isinstance(payload, dict)
    }


# ---------------------------------------------------------------------------
# Profile management API
# ---------------------------------------------------------------------------


def current_profile() -> str:
    """Return the name of the active profile."""
    return _profile_state["current"]


def list_profiles() -> list[str]:
    """Return the names of every profile currently registered."""
    return list(_profile_state["available"])


def create_profile(name: str, copy_from_current: bool = False) -> bool:
    """Create a new profile. Empty by default; ``copy_from_current`` clones the active one."""
    name = (name or "").strip()
    if not name or name in _profile_state["available"]:
        return False
    cancel_pending_save()
    write_user_setting()  # ensure current state is persisted before we touch the file
    path = _user_settings_path()
    payload = read_json(str(path)) if path.exists() else None
    if not isinstance(payload, dict) or "profiles" not in payload:
        payload = {"current_profile": current_profile(), "profiles": {}}
    seed = dict(user_setting_dict) if copy_from_current else {}
    payload["profiles"][name] = seed
    write_json(str(path), payload)
    _profile_state["available"].append(name)
    return True


def delete_profile(name: str) -> bool:
    """Remove a profile from disk. The default + active profiles cannot be deleted."""
    if name == DEFAULT_PROFILE or name == current_profile():
        return False
    if name not in _profile_state["available"]:
        return False
    cancel_pending_save()
    write_user_setting()
    path = _user_settings_path()
    if path.exists():
        payload = read_json(str(path))
        if isinstance(payload, dict) and "profiles" in payload:
            payload["profiles"].pop(name, None)
            write_json(str(path), payload)
    _profile_state["available"].remove(name)
    return True


def rename_profile(old: str, new: str) -> bool:
    """Rename ``old`` to ``new``. Default and active profiles can be renamed."""
    new = (new or "").strip()
    if (
        not new
        or new in _profile_state["available"]
        or old not in _profile_state["available"]
        or old == new
    ):
        return False
    cancel_pending_save()
    write_user_setting()
    path = _user_settings_path()
    if not path.exists():
        return False
    payload = read_json(str(path))
    if not isinstance(payload, dict) or "profiles" not in payload:
        return False
    profiles = payload["profiles"]
    if old not in profiles:
        return False
    profiles[new] = profiles.pop(old)
    if payload.get("current_profile") == old:
        payload["current_profile"] = new
        _profile_state["current"] = new
    write_json(str(path), payload)
    available = _profile_state["available"]
    available[available.index(old)] = new
    return True


def switch_profile(name: str) -> bool:
    """Activate ``name``: persist the current profile, load the new one's data."""
    if name not in _profile_state["available"]:
        return False
    if name == current_profile():
        return True
    cancel_pending_save()
    write_user_setting()
    path = _user_settings_path()
    if not path.exists():
        return False
    payload = read_json(str(path))
    if not isinstance(payload, dict) or "profiles" not in payload:
        return False
    new_data = payload["profiles"].get(name, {})
    if not isinstance(new_data, dict):
        new_data = {}
    user_setting_dict.clear()
    user_setting_dict.update(new_data)
    _profile_state["current"] = name
    write_user_setting()  # persist the new current pointer
    return True


# ---------------------------------------------------------------------------
# Low-level JSON I/O
# ---------------------------------------------------------------------------


def read_json(json_file_path: str) -> Any | None:
    """
    use to read action file
    :param json_file_path JSON file's path to read
    """
    _lock.acquire()
    try:
        file_path = Path(json_file_path)
        if file_path.exists() and file_path.is_file():
            with open(json_file_path, encoding="utf-8") as read_file:
                return json.loads(read_file.read())
    except Exception as e:
        _settings_logger.debug(f"Failed to read {json_file_path}: {e}")
    finally:
        _lock.release()


def write_json(json_save_path: str, data_to_output: dict | list) -> None:
    """
    Atomic JSON writer — writes to a .tmp sibling then os.replace() so a crash
    mid-write never leaves a half-written settings file.

    :param json_save_path  JSON save path
    :param data_to_output JSON data to output
    """
    _lock.acquire()
    tmp_path: Path | None = None
    try:
        path = Path(json_save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as file_to_write:
            file_to_write.write(json.dumps(data_to_output, indent=4, ensure_ascii=False))
        # os.replace is atomic on both POSIX and Windows (since Python 3.3).
        os.replace(tmp_path, path)
        tmp_path = None
    except Exception as e:
        _settings_logger.error(f"Failed to write {json_save_path}: {e}")
    finally:
        # Clean up orphan tmp on failure
        if tmp_path is not None:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
        _lock.release()
