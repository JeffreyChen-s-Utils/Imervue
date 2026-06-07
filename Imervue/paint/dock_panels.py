"""Paint workspace dock panels — facade re-exporting the docks package.

Individual docks live in ``Imervue.paint.docks``; re-exported here so existing
``from Imervue.paint.dock_panels import LayerDock`` imports keep working.
"""
from __future__ import annotations

from Imervue.paint.docks._helpers import _strip_color_chip
from Imervue.paint.docks.brushes import BrushDock, FillDock
from Imervue.paint.docks.color import ColorDock
from Imervue.paint.docks.layers import LayerDock
from Imervue.paint.docks.materials import MaterialDock, _MaterialThumbnailButton
from Imervue.paint.docks.navigators import (
    HistoryDock,
    NavigatorDock,
    PageNavigatorDock,
)

__all__ = [
    "BrushDock", "ColorDock", "FillDock", "HistoryDock", "LayerDock",
    "MaterialDock", "NavigatorDock", "PageNavigatorDock",
    "_MaterialThumbnailButton", "_strip_color_chip",
]
