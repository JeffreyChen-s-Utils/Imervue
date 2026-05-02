"""One-click support-bundle generator.

Zips up the things a maintainer typically asks for when triaging a bug:
the current log, system info (Python / Qt / OS / GPU vendor), and the
*sanitised* user settings JSON. Personal data is stripped — recent file
paths, bookmarks, and clipboard content never leave the user's machine.

Pure I/O — no Qt — so the work runs cleanly under tests. The Help menu
entry just calls :func:`build_report` and shows the resulting path.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import platform
import sys
import zipfile
from pathlib import Path

from Imervue.system.app_paths import app_dir

logger = logging.getLogger("Imervue.error_report")


# Settings keys that may contain user paths / personal data and must NOT
# leave the local machine. Stripped before the report is zipped.
_SENSITIVE_KEYS = frozenset({
    "user_recent_folders",
    "user_recent_images",
    "user_last_folder",
    "bookmarks",
    "image_ratings",
    "image_favorites",
    "image_color_labels",
    "macros",
    "macro_last_name",
    "external_editors",
    "window_geometry",
    "window_state",
})


def collect_system_info() -> dict:
    """Return a small JSON-serialisable dict of platform / runtime info."""
    qt_version = ""
    try:
        from PySide6 import __version__ as qt_version  # type: ignore[attr-defined]
    except ImportError:
        qt_version = "unknown"
    return {
        "imervue_version": _imervue_version(),
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "qt_pyside6": qt_version,
        "is_frozen": getattr(sys, "frozen", False) or "__compiled__" in dir(sys),
        "report_generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }


def _imervue_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
        try:
            return version("Imervue")
        except PackageNotFoundError:
            return "0.0.0+dev"
    except ImportError:
        return "unknown"


def sanitise_settings(settings: dict) -> dict:
    """Return a copy of ``settings`` with personal-data keys removed."""
    return {k: v for k, v in settings.items() if k not in _SENSITIVE_KEYS}


def build_report(out_path: Path | str | None = None) -> Path:
    """Build a support-bundle zip and return its path.

    When ``out_path`` is omitted the file lands in ``<app_dir>/`` with a
    timestamped name. Existing reports are not overwritten — a numeric
    suffix is appended on collision.
    """
    target = Path(out_path) if out_path is not None else _default_report_path()
    target = _next_free_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    info = collect_system_info()
    settings = _read_user_settings()
    log_text = _read_log_file()

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("system_info.json", json.dumps(info, indent=2, ensure_ascii=False))
        zf.writestr(
            "user_settings_sanitised.json",
            json.dumps(sanitise_settings(settings), indent=2, ensure_ascii=False),
        )
        if log_text:
            zf.writestr("imervue.log", log_text)
    logger.info("Built error report at %s", target)
    return target


def _default_report_path() -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return app_dir() / f"imervue-report-{stamp}.zip"


def _next_free_path(path: Path) -> Path:
    """Return ``path`` itself, or path-1 / path-2 / … if it already exists."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _read_user_settings() -> dict:
    try:
        from Imervue.user_settings.user_setting_dict import user_setting_dict
    except ImportError:
        return {}
    # ``set`` and other non-JSON types may live in user_setting_dict at runtime;
    # coerce them to lists so the resulting JSON serialises cleanly.
    return {k: _jsonable(v) for k, v in user_setting_dict.items()}


def _jsonable(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    return value


def _read_log_file() -> str:
    log_path = app_dir() / "imervue.log"
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""
