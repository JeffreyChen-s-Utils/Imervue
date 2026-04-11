import json
import logging
import os
import threading
from pathlib import Path
from threading import Lock
from typing import Dict, Any, Optional, Union

from Imervue.system.app_paths import user_settings_path as _user_settings_path

# 使用者設定的全域字典
# Global dictionary for user settings
user_setting_dict: Dict[str, Any] = {
    "language": "English",
    "user_recent_folders": [],
    "user_recent_images": [],
    "user_last_folder": "",
    "bookmarks": [],
}

_lock = Lock()

# ---------------------------------------------------------------------------
# Debounced background save
# ---------------------------------------------------------------------------
# 任何一次設定變動都應該呼叫 schedule_save()。它會把真正的寫入延後 _SAVE_DEBOUNCE_SEC
# 秒，期間若再被呼叫就重置計時，避免高頻變動（評分、收藏、拖曳選取）瘋狂寫檔。
# 真正落地時會用 atomic write（tmp + os.replace），避免寫到一半斷電留下殘缺 JSON。

_SAVE_DEBOUNCE_SEC = 2.0
_save_timer: Optional[threading.Timer] = None
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


def write_user_setting() -> Path:
    """
    將使用者設定寫入 JSON 檔案
    Write user settings into JSON file

    :return: 設定檔路徑 (Path to the settings file)
    """
    user_setting_file = _user_settings_path()
    write_json(str(user_setting_file), user_setting_dict)
    return user_setting_file


def read_user_setting() -> Path:
    """
    讀取使用者設定檔，並更新全域字典
    Read user settings from JSON file and update global dictionary

    :return: 設定檔路徑 (Path to the settings file)
    """
    user_setting_file = _user_settings_path()
    if user_setting_file.exists() and user_setting_file.is_file():
        data = read_json(str(user_setting_file))
        if isinstance(data, dict):
            user_setting_dict.update(data)
    return user_setting_file


def read_json(json_file_path: str) -> Optional[Any]:
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


def write_json(json_save_path: str, data_to_output: Union[dict, list]) -> None:
    """
    Atomic JSON writer — writes to a .tmp sibling then os.replace() so a crash
    mid-write never leaves a half-written settings file.

    :param json_save_path  JSON save path
    :param data_to_output JSON data to output
    """
    _lock.acquire()
    tmp_path: Optional[Path] = None
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
