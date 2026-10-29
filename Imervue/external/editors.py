"""
External editor launcher.

Configured editors are stored in ``user_setting_dict["external_editors"]`` as a
list of plain dicts (JSON-safe). Each entry pairs a display name with an
executable path. Launching uses non-blocking ``subprocess.Popen`` with
``shell=False``. Windows may still interpret batch files through a shell.
"""
from __future__ import annotations

import logging
import shlex
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

from Imervue.user_settings.user_setting_dict import user_setting_dict, schedule_save

logger = logging.getLogger("Imervue.external_editors")

_SETTINGS_KEY = "external_editors"


@dataclass(frozen=True)
class EditorEntry:
    """One configured external editor."""
    name: str
    executable: str
    arguments: str = ""  # extra CLI args; {path} is substituted with the image

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> EditorEntry | None:
        """Parse one entry, returning None on invalid input."""
        if not isinstance(data, dict):
            return None
        name = data.get("name", "")
        exe = data.get("executable", "")
        if not isinstance(name, str) or not isinstance(exe, str):
            return None
        if not name.strip() or not exe.strip():
            return None
        extra = data.get("arguments", "")
        if not isinstance(extra, str):
            extra = ""
        return cls(name=name.strip(), executable=exe.strip(), arguments=extra)


def load_editors() -> list[EditorEntry]:
    """Return configured editors. Unknown entries are silently dropped."""
    raw = user_setting_dict.get(_SETTINGS_KEY, [])
    if not isinstance(raw, list):
        return []
    return list(filter(None, map(EditorEntry.from_dict, raw)))


def save_editors(editors: list[EditorEntry]) -> None:
    """Persist ``editors`` to user settings."""
    user_setting_dict[_SETTINGS_KEY] = [e.to_dict() for e in editors]
    schedule_save()


def _build_argv(entry: EditorEntry, image_path: str) -> list[str]:
    """Build the argument vector, substituting ``{path}`` if the user set it."""
    extra = entry.arguments.strip()
    tokens = shlex.split(extra, posix=sys.platform != "win32")
    if "{path}" in extra:
        tokens = [tok.replace("{path}", image_path) for tok in tokens]
    else:
        tokens.append(image_path)
    return [entry.executable, *tokens]


def launch_editor(entry: EditorEntry, image_path: str) -> bool:
    """Launch ``entry`` for ``image_path``. Returns True if the process started."""
    path_obj = Path(image_path)
    if not path_obj.is_file():
        logger.warning("External editor: file not found: %s", image_path)
        return False
    exe = Path(entry.executable)
    if not exe.is_file():
        logger.warning("External editor executable missing: %s", entry.executable)
        return False
    argv = _build_argv(entry, str(path_obj))
    try:
        subprocess.Popen(argv, shell=False)  # noqa: S603 - user-configured path
    except OSError as exc:
        logger.exception("Failed to launch %s: %s", entry.name, exc)
        return False
    return True
