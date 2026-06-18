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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
)

from Imervue.image.gps import collect_gps
from Imervue.image.reverse_geocode import reverse_geocode
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

logger = logging.getLogger("Imervue.map_view_dialog")

_UNKNOWN_PLACE = "Unknown"

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


@dataclass(frozen=True)
class PlaceGroup:
    """Photos sharing a nearest-city place name, plotted as one marker."""

    place: str
    lat: float
    lon: float
    count: int
    paths: tuple[str, ...]


def group_points_by_place(
    points: list[tuple[str, float, float]],
) -> list[PlaceGroup]:
    """Cluster ``(path, lat, lon)`` points by their nearest-city place name.

    Each group's marker sits at the mean coordinate of its members. Groups are
    ordered by descending count (then place name) for a stable, useful order.
    """
    buckets: dict[str, list[tuple[str, float, float]]] = {}
    for path, lat, lon in points:
        place = reverse_geocode(lat, lon) or _UNKNOWN_PLACE
        buckets.setdefault(place, []).append((path, lat, lon))
    groups = [
        PlaceGroup(
            place=place,
            lat=sum(item[1] for item in items) / len(items),
            lon=sum(item[2] for item in items) / len(items),
            count=len(items),
            paths=tuple(item[0] for item in items),
        )
        for place, items in buckets.items()
    ]
    groups.sort(key=lambda group: (-group.count, group.place))
    return groups


def _collect_library_paths(ui: ImervueMainWindow) -> list[str]:
    viewer = getattr(ui, "viewer", None)
    model = getattr(viewer, "model", None)
    images = getattr(model, "images", None)
    return list(images) if images else []


def _render_html(groups: list[PlaceGroup]) -> str:
    items = [
        {"lat": g.lat, "lon": g.lon,
         "label": html.escape(f"{g.place} ({g.count})")}
        for g in groups
    ]
    return _LEAFLET_HTML.replace("__POINTS__", json.dumps(items))


class MapViewDialog(QDialog):
    def __init__(self, ui: ImervueMainWindow):
        super().__init__(ui)
        self._ui = ui
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("map_title", "Map View"))
        self.resize(900, 640)

        paths = _collect_library_paths(ui)
        self._points = collect_gps(paths)
        self._groups = group_points_by_place(self._points)

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
            for group in self._groups:
                lst.addItem(
                    f"{group.place} ({group.count})  —  "
                    f"{group.lat:.5f}, {group.lon:.5f}",
                )
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
        view.setHtml(_render_html(self._groups))
        return view


def open_map_view(ui: ImervueMainWindow) -> None:
    MapViewDialog(ui).exec()
