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
    GIMP_PALETTE_EXTENSION,
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
    for key, fallback, slot in (
        ("paint_file_import_brush_preset", "Import brush preset…",
         bridge.import_brush_preset),
        ("paint_file_import_palette", "Import palette…",
         bridge.import_palette),
        (None, None, None),
        ("paint_file_export_image", "Export image…",
         bridge.export_active_image),
        ("paint_file_export_pages_cbz", "Export pages → CBZ…",
         bridge.export_pages_cbz),
        ("paint_file_export_pages_pdf", "Export pages → PDF…",
         bridge.export_pages_pdf),
    ):
        if key is None:
            menu.addSeparator()
            continue
        action = menu.addAction(lang.get(key, fallback))
        action.triggered.connect(slot)


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

    # ---- import paths ----------------------------------------------------

    def import_brush_preset(self) -> None:  # pragma: no cover - QFileDialog
        path = self._pick_file(
            title_key="paint_file_import_brush_preset",
            title_fallback="Import brush preset",
            filters=[
                f"Imervue brush (*{IMERVUE_BRUSH_EXTENSION})",
                f"MediBang brush (*{MEDIBANG_BRUSH_EXTENSION})",
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
                f"GIMP palette (*{GIMP_PALETTE_EXTENSION})",
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
            filter=_image_filter_for(preset.format),
        )
        if not path:
            return
        try:
            self._write_image_at_path(composite, path, preset)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_export_image", exc)

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
            filter="Comic Book Zip (*.cbz)",
        )
        if not path:
            return
        from Imervue.paint.paint_project_export import export_project_cbz
        try:
            export_project_cbz(project, path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_export_pages_cbz", exc)

    def export_pages_pdf(self) -> None:  # pragma: no cover - QFileDialog
        project = self._current_project()
        if project is None:
            return
        path = self._pick_save_file(
            title_key="paint_file_export_pages_pdf",
            title_fallback="Export pages → PDF",
            filter="PDF (*.pdf)",
        )
        if not path:
            return
        from Imervue.paint.paint_project_export import export_project_pdf
        try:
            export_project_pdf(project, path)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_export_pages_pdf", exc)

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
        self, *, title_key: str, title_fallback: str, filter: str,
    ) -> str | None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getSaveFileName(
            self._workspace,
            lang.get(title_key, title_fallback),
            "",
            filter,
        )
        return path or None

    def _warn(self, title_key: str, exc: Exception) -> None:  # pragma: no cover
        lang = language_wrapper.language_word_dict
        QMessageBox.warning(
            self._workspace,
            lang.get(title_key, "Error"),
            str(exc),
        )


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
