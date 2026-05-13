"""File menu wiring — import / export entries for the Paint workspace.

Each verb in the engine layer (brush_preset_io, color_palette_io,
paint_project_export, export_presets) gets a one-click entry here.
The file dialogs are routed through Qt's ``QFileDialog`` so the
user picks paths via the OS native browser; the engine modules do
the actual reading / writing.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint.brush_preset_io import (
    IMERVUE_BRUSH_EXTENSION,
    MEDIBANG_BRUSH_EXTENSION,
    import_bundle,
)
from Imervue.paint.brush_presets import save_brush_presets
from Imervue.paint.color_palette_io import (
    ADOBE_COLOR_EXTENSION,
    ADOBE_SWATCH_EXCHANGE_EXTENSION,
    GPL_PALETTE_EXTENSION,
    import_palette,
)
from Imervue.paint.export_presets import (
    BUILT_IN_EXPORT_PRESETS,
    all_export_presets,
)
from Imervue.paint.paint_menu_bar import menu_for

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace

logger = logging.getLogger("Imervue.paint.file_menu")


def populate_file_menu(workspace: PaintWorkspace) -> None:
    """Attach the documented File-menu actions to ``workspace``.

    The workspace is responsible for keeping references to the
    helper bridge instances; we hang the bridge on the workspace as
    ``_file_menu_bridge`` so callers can hit the same verbs via
    keyboard shortcut without re-instantiating the helpers.
    """
    bridge = _FileMenuBridge(workspace)
    workspace._file_menu_bridge = bridge   # noqa: SLF001
    menu = menu_for(workspace, "file")
    lang = language_wrapper.language_word_dict
    from PySide6.QtGui import QKeySequence
    for key, fallback, slot, shortcut in (
        ("paint_file_new_tab", "New Tab",
         bridge.new_tab, "Ctrl+N"),
        ("paint_file_new_project", "New Comic Project…",
         bridge.new_comic_project, "Ctrl+Shift+N"),
        ("paint_file_close_tab", "Close Tab",
         bridge.close_active_tab, "Ctrl+W"),
        (None, None, None, None),
        ("paint_file_open_psd", "Open PSD…",
         bridge.open_psd, "Ctrl+O"),
        ("paint_file_save_psd", "Save as PSD…",
         bridge.save_psd, "Ctrl+S"),
        (None, None, None, None),
        ("paint_file_import_brush_preset", "Import brush preset…",
         bridge.import_brush_preset, ""),
        ("paint_file_import_palette", "Import palette…",
         bridge.import_palette, ""),
        (None, None, None, None),
        ("paint_file_export_image", "Export image…",
         bridge.export_active_image, ""),
        ("paint_file_export_pages_cbz", "Export pages → CBZ…",
         bridge.export_pages_cbz, ""),
        ("paint_file_export_pages_pdf", "Export pages → PDF…",
         bridge.export_pages_pdf, ""),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)

    # File ▸ Recent submenu — rebuilt every time it's shown so the
    # latest opens land at the top without having to re-tear-down
    # the whole menu. Cleared / Open Recent paths route through
    # the bridge so the same engine call services both new opens
    # and recent reopens (preserves the "added to recent" path).
    recent_menu = menu.addMenu(
        lang.get("paint_file_recent", "Recent"),
    )
    bridge._recent_menu = recent_menu   # noqa: SLF001
    recent_menu.aboutToShow.connect(bridge.refresh_recent_menu)
    bridge.refresh_recent_menu()


# ---------------------------------------------------------------------------
# Bridge — file dialogs + engine calls
# ---------------------------------------------------------------------------


class _FileMenuBridge:
    """Stateless-ish glue between the menu actions and engine verbs.

    Kept as a class instead of free functions so the workspace can
    hold a single reference (preventing the bound-method instances
    from getting GC'd between menu builds).
    """

    def __init__(self, workspace: PaintWorkspace):
        self._workspace = workspace

    # ---- multi-document tabs --------------------------------------------

    def new_tab(self) -> None:
        self._workspace.new_tab()

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

    def close_active_tab(self) -> None:
        # ``_tabs`` is the workspace-private QTabWidget — bridge talks
        # to the public ``close_tab(index)`` so we don't have to duplicate
        # the "refuse to close the last tab" rule here.
        index = self._workspace._tabs.currentIndex()  # noqa: SLF001
        self._workspace.close_tab(index)

    # ---- recent files ---------------------------------------------------

    def refresh_recent_menu(self) -> None:
        """Rebuild the File ▸ Recent submenu from the persisted list.

        Keeps the truncation simple: when no recents exist a single
        disabled placeholder entry shows so the submenu doesn't look
        broken; when entries exist, the bottom row offers Clear.
        """
        from Imervue.paint import recent_files

        recent_menu = getattr(self, "_recent_menu", None)
        if recent_menu is None:
            return
        recent_menu.clear()
        lang = language_wrapper.language_word_dict
        entries = recent_files.paths()
        if not entries:
            placeholder = recent_menu.addAction(
                lang.get("paint_file_recent_empty", "(no recent files)"),
            )
            placeholder.setEnabled(False)
            return
        for path in entries:
            label = self._format_recent_label(path)
            action = recent_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, p=path: self.open_psd_at(p),
            )
        recent_menu.addSeparator()
        clear_action = recent_menu.addAction(
            lang.get("paint_file_recent_clear", "Clear recent files"),
        )
        clear_action.triggered.connect(self._on_clear_recent)

    def _on_clear_recent(self) -> None:
        from Imervue.paint import recent_files
        recent_files.clear()
        self.refresh_recent_menu()

    @staticmethod
    def _format_recent_label(path: str) -> str:
        """Turn an absolute path into a short menu label.

        Show the file name plus the parent directory so the user can
        disambiguate two files with the same name in different
        folders without showing the full absolute path.
        """
        import os
        head, tail = os.path.split(path)
        if not tail:
            return path
        parent = os.path.basename(head)
        if parent:
            return f"{tail}    [{parent}]"
        return tail

    # ---- PSD interop ----------------------------------------------------

    def open_psd(self) -> None:  # pragma: no cover - QFileDialog
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self._workspace,
            language_wrapper.language_word_dict.get(
                "paint_file_open_psd", "Open PSD",
            ),
            "",
            "Photoshop (*.psd)",
        )
        if not path:
            return
        self.open_psd_at(path)

    def open_psd_at(self, path: str) -> None:
        """Open ``path`` and add it to the recent-files list.

        Centralised entry point for both the file-dialog open and the
        File ▸ Recent submenu reopen, so every successful open feeds
        the recent list through one code path.
        """
        from Imervue.paint import recent_files
        commit_open_psd(self._workspace, path)
        recent_files.add(str(path))
        self.refresh_recent_menu()

    def save_psd(self) -> None:  # pragma: no cover - QFileDialog
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self._workspace,
            language_wrapper.language_word_dict.get(
                "paint_file_save_psd", "Save as PSD",
            ),
            "",
            "Photoshop (*.psd)",
        )
        if not path:
            return
        try:
            from Imervue.paint.psd_io import save_psd
            document = self._workspace.canvas().document()
            if document.shape is None:
                return
            save_psd(document, path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_save_psd", exc)
            return
        self._notify_success("paint_file_save_psd_done", "Saved PSD", path)

    # ---- import paths ----------------------------------------------------

    def import_brush_preset(self) -> None:  # pragma: no cover - QFileDialog
        path = self._pick_file(
            title_key="paint_file_import_brush_preset",
            title_fallback="Import brush preset",
            filters=[
                f"Imervue brush (*{IMERVUE_BRUSH_EXTENSION})",
                f"raster paint apps brush (*{MEDIBANG_BRUSH_EXTENSION})",
            ],
        )
        if not path:
            return
        try:
            presets = import_bundle(path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_import_brush_preset", exc)
            return
        if presets:
            save_brush_presets(presets)

    def import_palette(self) -> None:  # pragma: no cover - QFileDialog
        path = self._pick_file(
            title_key="paint_file_import_palette",
            title_fallback="Import palette",
            filters=[
                f"external image editors palette (*{GPL_PALETTE_EXTENSION})",
                f"Adobe Swatch (*{ADOBE_COLOR_EXTENSION})",
                f"Adobe Swatch Exchange (*{ADOBE_SWATCH_EXCHANGE_EXTENSION})",
            ],
        )
        if not path:
            return
        try:
            colours = import_palette(path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_import_palette", exc)
            return
        if not colours:
            return
        # Push every imported colour into the colour-history channel
        # so the SwatchPanel + ColorDock pick them up immediately.
        state = self._workspace.state()
        for colour in colours:
            state.set_foreground(colour.rgb, commit=True)

    # ---- export paths ----------------------------------------------------

    def export_active_image(self) -> None:  # pragma: no cover - QFileDialog
        composite = self._workspace.canvas().document().composite()
        if composite is None:
            return
        preset = _default_export_preset()
        path = self._pick_save_file(
            title_key="paint_file_export_image",
            title_fallback="Export image",
            name_filter=_image_filter_for(preset.format),
        )
        if not path:
            return
        try:
            self._write_image_at_path(composite, path, preset)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_export_image", exc)
            return
        self._notify_success("paint_file_export_image_done", "Exported", path)

    def _write_image_at_path(self, composite, path, preset) -> None:
        """Write ``composite`` to the exact ``path`` the user chose.

        The export-preset's filename template is for batch flows; the
        single-image action expects whatever the user typed in the save
        dialog to be the literal output filename. We therefore drop
        through Pillow directly with the preset's format / quality /
        resolution settings.
        """
        from pathlib import Path

        from Imervue.paint.export_presets import _write_with_format
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_with_format(
            composite, target, preset.format,
            int(preset.quality), int(preset.max_resolution),
        )

    def export_pages_cbz(self) -> None:  # pragma: no cover - QFileDialog
        project = self._current_project()
        if project is None:
            return
        path = self._pick_save_file(
            title_key="paint_file_export_pages_cbz",
            title_fallback="Export pages → CBZ",
            name_filter="Comic Book Zip (*.cbz)",
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

    # ---- helpers (testable) ---------------------------------------------

    def _current_project(self):
        """Return the host's PaintProject or ``None``.

        The workspace doesn't yet own a multi-page project — this is
        the seam where a future "open project" command will plug in.
        For now we return ``None`` so the export actions short-circuit
        cleanly instead of crashing.
        """
        return getattr(self._workspace, "_project", None)

    def _pick_file(  # pragma: no cover - QFileDialog
        self, *, title_key: str, title_fallback: str, filters: list[str],
    ) -> str | None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self._workspace,
            lang.get(title_key, title_fallback),
            "",
            ";;".join(filters),
        )
        return path or None

    def _pick_save_file(  # pragma: no cover - QFileDialog
        self, *, title_key: str, title_fallback: str, name_filter: str,
    ) -> str | None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self._workspace,
            lang.get(title_key, title_fallback),
            "",
            name_filter,
        )
        return path or None

    def _notify_success(
        self, key: str, fallback: str, path: str,
    ) -> None:
        """Pop a non-blocking success toast for a file write that
        completed cleanly.

        Marks the active tab clean (clears the "modified" asterisk
        + the close-prompt) since the user just persisted their
        work. Falls back to the status bar's transient message when
        the workspace has no toast manager (very early bootstrap or
        a unit-test stub) so the success signal is never silent.
        """
        from pathlib import Path
        lang = language_wrapper.language_word_dict
        verb = lang.get(key, fallback)
        msg = f"{verb}: {Path(path).name}"
        mark_clean = getattr(self._workspace, "mark_active_tab_clean", None)
        if callable(mark_clean):
            mark_clean()
        toast = getattr(self._workspace, "toast", None)
        if toast is not None:
            toast.success(msg)
            return
        status = getattr(self._workspace, "_status", None)
        if status is not None:
            status.showMessage(msg, 3000)

    def _warn(self, title_key: str, exc: Exception) -> None:
        """Surface a file-operation error.

        Prefers a non-blocking toast notification when the workspace
        has one (every paint workspace built since the toast wiring
        landed) so failed exports / imports don't interrupt the
        artist's flow with a modal that has to be dismissed. Falls
        back to ``QMessageBox.warning`` for older callers that
        construct the bridge without a fully-wired workspace
        (legacy tests, embedded contexts).
        """
        lang = language_wrapper.language_word_dict
        title = lang.get(title_key, "Error")
        toast = getattr(self._workspace, "toast", None)
        if toast is not None:
            toast.error(f"{title}: {exc}")
            return
        QMessageBox.warning(self._workspace, title, str(exc))


def _default_export_preset():
    """First built-in preset — the documented "PNG full quality" entry."""
    presets = all_export_presets()
    if presets:
        return presets[0]
    return BUILT_IN_EXPORT_PRESETS[0]


def _image_filter_for(format_tag: str) -> str:
    """QFileDialog filter string for a single output format."""
    return {
        "png": "PNG (*.png)",
        "jpeg": "JPEG (*.jpg *.jpeg)",
        "webp": "WebP (*.webp)",
        "bmp": "BMP (*.bmp)",
        "tiff": "TIFF (*.tif *.tiff)",
    }.get(format_tag, f"{format_tag.upper()} (*.{format_tag})")


# ---------------------------------------------------------------------------
# PSD commit helpers — pure logic, callable from tests without a dialog
# ---------------------------------------------------------------------------


def commit_open_psd(workspace, path: str) -> bool:
    """Load ``path`` as a PSD and replace the active document.

    Returns ``True`` on success, ``False`` for any decode failure
    (caller can show a non-modal error). Loaded PSDs land in a fresh
    tab when the workspace supports tabs so the open document isn't
    silently destroyed by the import.
    """
    from Imervue.paint.psd_io import load_psd
    try:
        new_doc = load_psd(path)
    except (OSError, ValueError):
        return False
    if new_doc.shape is None:
        return False
    composite = new_doc.composite()
    if composite is None:
        return False
    if hasattr(workspace, "new_tab"):
        canvas = workspace.new_tab()
        canvas.load_image(composite)
    else:
        workspace.load_image(composite)
    return True


def commit_save_psd(workspace, path: str) -> bool:
    """Write the active document to ``path``. Returns ``True`` on
    success, ``False`` when there's no document or save fails."""
    from Imervue.paint.psd_io import save_psd
    document = workspace.canvas().document()
    if document.shape is None:
        return False
    try:
        save_psd(document, path)
    except (OSError, ValueError):
        return False
    return True
