"""Comic-project verbs of the Paint File menu: new / open / save and page exports.

A mixin of :class:`Imervue.paint.file_menu._FileMenuBridge`; it relies on the
bridge's ``_workspace``, ``_pick_file``, ``_pick_save_file``, ``_warn`` and
``_notify_success``.
"""
from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from Imervue.gui.file_filters import translated_filter
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace


def _project_filter() -> str:
    """The file-dialog filter for comic project bundles."""
    from Imervue.paint.paint_project_io import PROJECT_FILE_EXTENSION
    return translated_filter("file_filter_comic_project", "Comic project",
                             (PROJECT_FILE_EXTENSION.lstrip("."),))


class FileMenuProjectsMixin:
    """File ▸ New / Open / Save Comic Project and Export pages → CBZ / PDF."""

    _workspace: PaintWorkspace

    def new_comic_project(self) -> None:  # pragma: no cover - Qt dialog
        """Pop a small picker (template + page count + project name)
        and bind the resulting :class:`PaintProject` to the workspace.

        Discoverability fix: previously the PageDock sat in its empty
        "no project" state forever because nothing in the UI created
        a project. This menu entry surfaces the comic-project flow.
        """
        from Imervue.paint.new_project_dialog import NewProjectDialog
        from Imervue.paint.page_templates import (
            project_from_template,
            template_by_name,
        )
        from PySide6.QtWidgets import QDialog

        dialog = NewProjectDialog(parent=self._workspace)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        choice = dialog.values()
        try:
            template = template_by_name(choice.template_name)
        except KeyError:
            return
        project = project_from_template(
            template,
            page_count=choice.page_count,
            project_name=choice.project_name,
            author=choice.author,
        )
        self._workspace.set_paint_project(project)

    def open_comic_project(self) -> None:  # pragma: no cover - QFileDialog
        path = self._pick_file(
            title_key="paint_file_open_project",
            title_fallback="Open Comic Project",
            filters=[_project_filter()],
        )
        if path:
            self.open_comic_project_at(path)

    def open_comic_project_at(self, path: str) -> bool:
        """Load the ``.imervue-proj`` at *path* and make it the workspace's project."""
        from Imervue.paint.paint_project_io import load_project
        try:
            project = load_project(path)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            self._warn("paint_file_open_project", exc)
            return False
        self._workspace.set_paint_project(project)
        self._notify_success("paint_file_open_project_done", "Opened comic project", path)
        return True

    def save_comic_project(self) -> None:  # pragma: no cover - QFileDialog
        if self._current_project() is None:
            self._warn("paint_file_save_project", language_wrapper.language_word_dict.get(
                "paint_file_no_project",
                "No comic project is open; File > New Comic Project… starts one."))
            return
        path = self._pick_save_file(
            title_key="paint_file_save_project",
            title_fallback="Save Comic Project",
            name_filter=_project_filter(),
        )
        if path:
            self.save_comic_project_to(path)

    def save_comic_project_to(self, path: str) -> bool:
        """Write the workspace's project, every page with its layers, to *path*.

        Adds the ``.imervue-proj`` extension when *path* has another one.
        """
        from Imervue.paint.paint_project_io import PROJECT_FILE_EXTENSION, save_project
        project = self._current_project()
        if project is None:
            return False
        if not path.lower().endswith(PROJECT_FILE_EXTENSION):
            path += PROJECT_FILE_EXTENSION
        try:
            save_project(project, path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_save_project", exc)
            return False
        self._notify_success("paint_file_save_project_done", "Saved comic project", path)
        return True

    def export_pages_cbz(self) -> None:  # pragma: no cover - QFileDialog
        project = self._current_project()
        if project is None:
            return
        path = self._pick_save_file(
            title_key="paint_file_export_pages_cbz",
            title_fallback="Export pages → CBZ",
            name_filter=translated_filter("file_filter_comic_zip", "Comic book archive", ("cbz",)),
        )
        if not path:
            return
        from Imervue.paint.paint_project_export import export_project_cbz
        try:
            export_project_cbz(project, path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_export_pages_cbz", exc)
            return
        self._notify_success(
            "paint_file_export_pages_cbz_done", "Exported CBZ", path,
        )

    def export_pages_pdf(self) -> None:  # pragma: no cover - QFileDialog
        project = self._current_project()
        if project is None:
            return
        path = self._pick_save_file(
            title_key="paint_file_export_pages_pdf",
            title_fallback="Export pages → PDF",
            name_filter="PDF (*.pdf)",
        )
        if not path:
            return
        from Imervue.paint.paint_project_export import export_project_pdf
        try:
            export_project_pdf(project, path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_export_pages_pdf", exc)
            return
        self._notify_success(
            "paint_file_export_pages_pdf_done", "Exported PDF", path,
        )

    def _current_project(self):
        """Return the host's :class:`PaintProject` or ``None``.

        The workspace stores it under ``_paint_project`` (set by
        :meth:`set_paint_project`, read by the page dock and manga menu). Reading
        the wrong attribute (``_project``) always returned ``None``, so Export
        Pages → CBZ / PDF silently no-opped even with a project open.
        """
        return getattr(self._workspace, "_paint_project", None)
