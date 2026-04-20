"""
Map view dialog — plot geotagged images on an OpenStreetMap background.

Uses QtWebEngine + Leaflet when available (rich interactive map); falls
back to a plain list of (path, lat, lon) tuples if QtWebEngine is not
installed — this keeps the feature usable without pulling in a large
optional dependency.
"""
from __future__ import annotations

import html
import json
import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
)

from Imervue.image.gps import collect_gps
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.map_view_dialog")

_LEAFLET_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{height:100%;margin:0;padding:0}</style>
</head><body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var points = __POINTS__;
var map = L.map('map');
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors', maxZoom: 19,
}).addTo(map);
var group = L.featureGroup();
points.forEach(function(p){
  var m = L.marker([p.lat, p.lon]);
  m.bindPopup(p.label);
  group.addLayer(m);
});
if (points.length) {
  group.addTo(map);
  map.fitBounds(group.getBounds().pad(0.2));
} else {
  map.setView([0, 0], 2);
}
</script></body></html>
"""


def _collect_library_paths(ui: "ImervueMainWindow") -> list[str]:
    viewer = getattr(ui, "viewer", None)
    model = getattr(viewer, "model", None)
    images = getattr(model, "images", None)
    return list(images) if images else []


def _render_html(points: list[tuple[str, float, float]]) -> str:
    items = [
        {"lat": lat, "lon": lon, "label": html.escape(path)}
        for path, lat, lon in points
    ]
    return _LEAFLET_HTML.replace("__POINTS__", json.dumps(items))


class MapViewDialog(QDialog):
    def __init__(self, ui: "ImervueMainWindow"):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("map_title", "Map View"))
        self.resize(900, 640)

        paths = _collect_library_paths(ui)
        self._points = collect_gps(paths)

        layout = QVBoxLayout(self)
        summary = lang.get(
            "map_count",
            "Plotting {n} geotagged image(s) of {total} scanned.",
        ).format(n=len(self._points), total=len(paths))
        layout.addWidget(QLabel(summary))

        web = self._try_build_web_view()
        if web is not None:
            layout.addWidget(web, 1)
        else:
            layout.addWidget(QLabel(lang.get(
                "map_fallback",
                "QtWebEngine is not installed — showing coordinates as a list.",
            )))
            lst = QListWidget()
            for path, lat, lon in self._points:
                lst.addItem(f"{lat:.5f}, {lon:.5f}  —  {path}")
            layout.addWidget(lst, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _try_build_web_view(self):
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            return None
        view = QWebEngineView(self)
        view.setHtml(_render_html(self._points))
        return view


def open_map_view(ui: "ImervueMainWindow") -> None:
    MapViewDialog(ui).exec()
