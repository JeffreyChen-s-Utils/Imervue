import json
from os import getcwd
from pathlib import Path
from threading import Lock
from typing import Dict, Any, Optional, Union

# 使用者設定的全域字典
# Global dictionary for user settings
user_setting_dict: Dict[str, Any] = {
    "language": "English",
    "user_recent_folders": [],
    "user_recent_images": [],
    "user_last_folder": ""
}

_lock = Lock()

def write_user_setting() -> Path:
    """
    將使用者設定寫入 JSON 檔案
    Write user settings into JSON file

    :return: 設定檔路徑 (Path to the settings file)
    """
    user_setting_file = Path(getcwd()) / "user_setting.json"
    write_json(str(user_setting_file), user_setting_dict)
    return user_setting_file


def read_user_setting() -> Path:
    """
    讀取使用者設定檔，並更新全域字典
    Read user settings from JSON file and update global dictionary

    :return: 設定檔路徑 (Path to the settings file)
    """
    user_setting_file = Path(getcwd()) / "user_setting.json"
    if user_setting_file.exists() and user_setting_file.is_file():
        user_setting_dict.update(read_json(str(user_setting_file)))
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
            with open(json_file_path) as read_file:
                return json.loads(read_file.read())
    finally:
        _lock.release()


def write_json(json_save_path: str, data_to_output: Union[dict, list]) -> None:
    """
    use to save action file
    :param json_save_path  JSON save path
    :param data_to_output JSON data to output
    """
    _lock.acquire()
    try:
        with open(json_save_path, "w+") as file_to_write:
            file_to_write.write(json.dumps(data_to_output, indent=4))
    finally:
        _lock.release()