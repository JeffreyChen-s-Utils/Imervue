"""Import and export verbs of the Paint File menu: brush presets, palettes, Export image….

A mixin of :class:`Imervue.paint.file_menu._FileMenuBridge`, plus the pure
export-format helpers the Export image… entry uses.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from Imervue.gui.file_filters import translated_filter
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
from Imervue.paint.document_status import document_status, refresh_document_status

if TYPE_CHECKING:
    from Imervue.paint.paint_workspace import PaintWorkspace

# Export image…: the file types offered, PNG first (the default), and the
# format each suffix names. A lossy format is written at full size, quality 95.
EXPORT_IMAGE_FILTER = ";;".join((
    "PNG (*.png)", "JPEG (*.jpg *.jpeg)", "WebP (*.webp)", "TIFF (*.tif *.tiff)", "BMP (*.bmp)",
))
_EXPORT_SUFFIX_FORMATS = {
    ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp",
    ".tif": "tiff", ".tiff": "tiff", ".bmp": "bmp",
}
_EXPORT_QUALITY = 95


def export_format_for(path: str) -> tuple[str, str]:
    """``(format, path)`` for an Export image target.

    The format its suffix names (case-insensitive); a path with another or no
    suffix is written as PNG with ``.png`` appended.
    """
    from pathlib import Path
    fmt = _EXPORT_SUFFIX_FORMATS.get(Path(path).suffix.lower())
    if fmt is None:
        return "png", f"{path}.png"
    return fmt, path


def write_export_image(composite, path: str, fmt: str) -> None:
    """Write the RGBA ``composite`` to ``path`` as ``fmt``, full size, in one step.

    JPEG has no alpha, so it is flattened onto white; the others keep it.
    Raises ``OSError`` / ``ValueError`` when the write fails.
    """
    from pathlib import Path

    from Imervue.paint.export_presets import _write_with_format
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_with_format(composite, target, fmt, _EXPORT_QUALITY, 0)


class FileMenuTransferMixin:
    """File ▸ Import brush preset… / Import palette… / Export image…."""

    _workspace: PaintWorkspace

    def import_brush_preset(self) -> None:  # pragma: no cover - QFileDialog
        path = self._pick_file(
            title_key="paint_file_import_brush_preset",
            title_fallback="Import brush preset",
            filters=[
                translated_filter("file_filter_imervue_brush", "Imervue brush",
                                  (IMERVUE_BRUSH_EXTENSION,)),
                translated_filter("file_filter_other_brush", "Brush from other paint apps",
                                  (MEDIBANG_BRUSH_EXTENSION,)),
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
                translated_filter("file_filter_other_palette", "Palette from other image editors",
                                  (GPL_PALETTE_EXTENSION,)),
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

    def export_active_image(self) -> None:
        """Flatten the active tab into the file the user picks, in the format its type names."""
        composite = self._workspace.canvas().document().composite()
        if composite is None:
            return
        path = self._pick_save_file(
            title_key="paint_file_export_image",
            title_fallback="Export image",
            name_filter=EXPORT_IMAGE_FILTER,
        )
        if not path:
            return
        fmt, path = export_format_for(path)
        try:
            write_export_image(composite, path, fmt)
        except (OSError, ValueError) as exc:
            self._warn("paint_file_export_image", exc)
            return
        self._notify_success("paint_file_export_image_done", "Exported", path)
        document_status(self._workspace.canvas()).exported_path = path
        refresh_document_status(self._workspace, self._workspace.canvas())
