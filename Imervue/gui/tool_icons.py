"""Scalable, palette-aware line icons for workspace tool palettes and actions."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

# A shared 24-unit grid keeps silhouettes, stroke weight and optical size consistent.
TOOL_GLYPHS = {
    "brush": '<path d="m14 4 6 6-8 8-6-6zM7 14c-5 0-1 5-5 7 6 1 9-2 7-5"/>',
    "eraser": '<path d="m13 3 8 8-10 10H7l-5-5zM7 11l8 8M11 21h11"/>',
    "fill": '<path d="m10 3 9 9-8 8-9-9zM3 12h15M7 2l7 7"/>'
            '<path d="M21 14c-1 2-3 4-3 5a3 3 0 0 0 6 0c0-1-2-3-3-5"/>',
    "eyedropper": '<path d="m15 3 6 6M14 6 3 17v4h4L18 10M12 8l4 4"/>',
    "select_rect": '<rect x="3" y="4" width="18" height="16" rx="1" '
                   'stroke-dasharray="3 3"/>',
    "select_lasso": '<path d="M8 18C-1 16 1 4 12 4s14 13 3 14H8c-4 0-5 5-1 4 3-1 3-5 1-6"/>',
    "select_wand": '<path d="m4 21 12-12M12 9l3 3M6 3v4M4 5h4M19 2v4M17 4h4M20 15v4M18 17h4"/>',
    "select_quick": '<circle cx="10" cy="12" r="8" stroke-dasharray="2 3"/>'
                    '<path d="m13 17 6-6 3 3-6 6-5 1z"/>',
    "move": '<path d="M12 2v20M2 12h20M8 6l4-4 4 4M8 18l4 4 4-4M6 8l-4 4 4 4M18 8l4 4-4 4"/>',
    "text": '<path d="M4 6V3h16v3M12 3v18M8 21h8"/>',
    "gradient": '<rect x="3" y="4" width="18" height="16" rx="2"/>'
                '<path d="M7 5v14M10 5v14M13 5v14M16 5v14" stroke-dasharray="1 2"/>',
    "blur": '<path d="M12 2C10 6 5 11 5 15a7 7 0 0 0 14 0c0-4-5-9-7-13Z"/>'
            '<path d="M8 15c0 3 2 4 4 4"/>',
    "smudge": '<path d="M8 13V5a2 2 0 0 1 4 0v7-2a2 2 0 0 1 4 0v3-1a2 2 0 0 1 4 0v5'
              'c0 4-2 5-6 5h-2c-3 0-5-4-8-7-2-2 1-4 3-2l3 3"/>',
    "dodge": '<circle cx="10" cy="10" r="6"/><path d="m14 14 7 7M7 10h6M10 7v6"/>',
    "burn": '<path d="M13 2c2 6-4 7-2 11 2-1 3-3 3-5 8 7 6 14-2 14-8 0-11-8-5-13'
            ' 0 4 1 5 2 5-2-5 3-7 4-12Z"/>',
    "sponge": '<path d="M5 5c3-4 4 1 8-1s8 1 8 5-3 4-1 8-3 6-7 4-6 3-9-1 0-5-1-8-1-5 2-7Z"/>'
              '<circle cx="8" cy="10" r="1"/><circle cx="15" cy="8" r="1"/>'
              '<circle cx="13" cy="16" r="1"/>',
    "bezier_pen": '<path d="m12 2 8 12-4 8H8l-4-8zM12 2v10M8 18h8"/>'
                  '<circle cx="12" cy="14" r="2"/>',
    "clone_stamp": '<path d="M5 15h14l2 6H3zM8 15v-3c0-2 2-3 1-6a3 3 0 1 1 6 0'
                   'c-1 3 1 4 1 6v3M6 22h12"/>',
    "speech_bubble": '<path d="M5 3h14a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H9l-6 3v-5'
                     'a3 3 0 0 1-1-2V6a3 3 0 0 1 3-3Z"/><path d="M7 8h10M7 13h6"/>',
    "shape_rect": '<rect x="3" y="4" width="18" height="16" rx="1"/>',
    "shape_ellipse": '<ellipse cx="12" cy="12" rx="10" ry="8"/>',
    "shape_line": '<path d="m4 20 16-16"/><circle cx="4" cy="20" r="1"/>'
                  '<circle cx="20" cy="4" r="1"/>',
    "shape_polygon": '<path d="m12 2 10 7-4 12H6L2 9Z"/>',
    "crop": '<path d="M7 2v15h15M2 7h15v15M3 21 21 3"/>',
    "transform": '<path d="M6 4h12M20 6v12M18 20H6M4 18V6"/>'
                 '<path d="M2 2h4v4H2zM18 2h4v4h-4zM2 18h4v4H2zM18 18h4v4h-4z"/>',
    "hand": '<path d="M8 13V5a2 2 0 0 1 4 0v7-8a2 2 0 0 1 4 0v8-5a2 2 0 0 1 4 0v8'
            'c0 5-2 7-7 7-4 0-6-4-9-8-1-2 1-4 3-2l3 3"/>',
    "zoom": '<circle cx="10" cy="10" r="7"/><path d="m15 15 7 7M6 10h8M10 6v8"/>',
}


_WORKSPACE_GLYPHS = {
    "arrow": '<path d="M4 20 20 4M8 4h12v12"/>',
    "mosaic": '<path d="M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z"/>',
    "rotate_ccw": '<path d="M3 10a9 9 0 1 1 1 8M3 3v7h7"/>',
    "rotate_cw": '<path d="M21 10a9 9 0 1 0-1 8M21 3v7h-7"/>',
    "flip_h": '<path d="M12 2v20M3 5v14l6-7zM21 5v14l-6-7z"/>',
    "flip_v": '<path d="M2 12h20M5 3h14l-7 6zM5 21h14l-7-6z"/>',
    "folder": '<path d="M2 7V4h7l3 3h10v13H2zM2 7h20"/>',
    "play": '<path d="m8 3 13 9-13 9z"/>',
    "save": '<path d="M3 3h15l3 3v15H3zM7 3v6h10V3M7 21v-8h10v8"/>',
}


class _ToolIconEngine(QIconEngine):
    def __init__(self, tool: str):
        super().__init__()
        self.tool = tool

    def clone(self):
        return _ToolIconEngine(self.tool)

    def paint(self, painter, rect, mode, state):
        palette = QApplication.palette()
        role = (QPalette.ColorRole.HighlightedText if state == QIcon.State.On
                else QPalette.ColorRole.Text)
        group = (QPalette.ColorGroup.Disabled if mode == QIcon.Mode.Disabled
                 else QPalette.ColorGroup.Active)
        colour = palette.color(group, role).name()
        glyph = (TOOL_GLYPHS | _WORKSPACE_GLYPHS)[self.tool]
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
               f'fill="none" stroke="{colour}" stroke-width="1.7" '
               f'stroke-linecap="round" stroke-linejoin="round">{glyph}</svg>')
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        side = min(rect.width(), rect.height())
        target = QRectF(rect.x() + (rect.width() - side) / 2,
                        rect.y() + (rect.height() - side) / 2, side, side)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, target)
        painter.restore()

    def pixmap(self, size: QSize, mode, state):
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        return pixmap


def tool_icon(tool: str) -> QIcon:
    """Return an icon that follows the current palette, selection and disabled state."""
    return QIcon(_ToolIconEngine(tool))
