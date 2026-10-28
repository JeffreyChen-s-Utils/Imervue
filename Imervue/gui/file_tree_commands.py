"""Create, rename, duplicate, and open filesystem items from the tree."""

from __future__ import annotations

from pathlib import Path
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.file_transfer import carry_along, carry_sidecars, is_same_file
from Imervue.gui.file_tree_paths import _next_duplicate_name
from Imervue.gui.file_tree_feedback import toast


def _create_new_folder(self, parent_dir: str) -> None:
    """Prompt for a folder name and create it under ``parent_dir``."""
    from PySide6.QtWidgets import QInputDialog

    lang = language_wrapper.language_word_dict
    name, ok = QInputDialog.getText(
        self,
        lang.get("tree_new_folder", "New Folder"),
        lang.get("tree_new_folder_prompt", "Folder name:"),
    )
    if not ok or not name.strip():
        return
    try:
        target = Path(parent_dir) / name.strip()
        target.mkdir(parents=False, exist_ok=False)
        self._refresh_tree()
    except FileExistsError:
        toast(self, "warning", lambda: lang.get("tree_folder_exists", "Folder already exists"))
        return
    except OSError as exc:
        toast(
            self,
            "error",
            lambda exc=exc: f"{lang.get('tree_new_folder_failed', 'Create failed')}: {exc}",
        )
        return
    toast(
        self,
        "success",
        lambda: lang.get("tree_new_folder_done", "Created folder {name}").format(name=target.name),
    )


def _rename_path(self, path: str) -> None:
    """Prompt for a new basename and rename the file or folder."""
    from PySide6.QtWidgets import QInputDialog

    lang = language_wrapper.language_word_dict
    target = Path(path)
    if not target.exists():
        return
    new_name, ok = QInputDialog.getText(
        self,
        lang.get("tree_rename", "Rename"),
        lang.get("tree_rename_prompt", "New name:"),
        text=target.name,
    )
    if not ok:
        return
    new_name = new_name.strip()
    if not new_name or new_name == target.name:
        return
    new_path = target.with_name(new_name)
    if new_path.exists() and not is_same_file(target, new_path):  # case-only is fine
        toast(
            self,
            "warning",
            lambda: lang.get("tree_rename_exists", "A file with that name already exists"),
        )
        return
    try:
        target.rename(new_path)
    except OSError as exc:
        toast(
            self,
            "error",
            lambda exc=exc: f"{lang.get('tree_rename_failed', 'Rename failed')}: {exc}",
        )
        return
    # Sidecars and saved ratings / tags follow (every file's, for a folder).
    carry_along([(str(target), str(new_path))], move=True)
    self._refresh_tree()
    toast(
        self,
        "success",
        lambda: lang.get("tree_rename_done", "Renamed to {name}").format(name=new_path.name),
    )


def _duplicate_file(self, path: str) -> None:
    """Copy ``path`` to a sibling with a "(copy)" suffix, its sidecars with it."""
    import shutil

    lang = language_wrapper.language_word_dict
    source = Path(path)
    if not source.is_file():
        return
    candidate = _next_duplicate_name(source)
    try:
        shutil.copy2(source, candidate)
    except OSError as exc:
        toast(
            self,
            "error",
            lambda exc=exc: f"{lang.get('tree_duplicate_failed', 'Duplicate failed')}: {exc}",
        )
        return
    carry_sidecars([(str(source), str(candidate))], move=False)
    self._refresh_tree()
    toast(
        self,
        "success",
        lambda: lang.get("tree_duplicate_done", "Duplicated to {name}").format(name=candidate.name),
    )


def _open_with_default_app(self, path: str) -> None:
    """Open ``path`` with the OS's default application via Qt's
    QDesktopServices, which is more portable than rolling per-OS
    subprocess calls. Surfaces a toast on failure so the artist
    knows whether the launch worked."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    url = QUrl.fromLocalFile(path)
    if QDesktopServices.openUrl(url):
        return
    lang = language_wrapper.language_word_dict
    toast(
        self,
        "error",
        lambda: lang.get(
            "tree_open_with_failed", "Couldn't open {name} with the default application"
        ).format(name=Path(path).name),
    )
