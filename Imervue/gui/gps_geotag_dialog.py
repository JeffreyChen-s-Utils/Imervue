"""GPS geotag editor — lat/lon input that writes EXIF GPS tags."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from Imervue.image.gps_geotag import write_gps
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.gps_geotag_dialog")


class GpsGeotagDialog(QDialog):
    def __init__(self, viewer: "GPUImageView", path: str):
        super().__init__(viewer)
        self._viewer = viewer
        self._path = path
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("geotag_title", "GPS Geotag"))
        self.setMinimumWidth(360)

        self._lat = QDoubleSpinBox()
        self._lat.setRange(-90.0, 90.0)
        self._lat.setDecimals(6)
        self._lat.setValue(0.0)
        self._lon = QDoubleSpinBox()
        self._lon.setRange(-180.0, 180.0)
        self._lon.setDecimals(6)
        self._lon.setValue(0.0)
        self._existing = self._load_existing()
        if self._existing is not None:
            self._lat.setValue(self._existing[0])
            self._lon.setValue(self._existing[1])

        form = QFormLayout()
        form.addRow(lang.get("geotag_lat", "Latitude (°):"), self._lat)
        form.addRow(lang.get("geotag_lon", "Longitude (°):"), self._lon)

        self._status = QLabel("")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._path))
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addWidget(buttons)

    def _load_existing(self) -> tuple[float, float] | None:
        try:
            from Imervue.image.gps import read_gps
        except ImportError:
            return None
        try:
            coords = read_gps(self._path)
        except (OSError, ValueError):
            return None
        return coords

    def _save(self) -> None:
        lang = language_wrapper.language_word_dict
        ok = write_gps(self._path, self._lat.value(), self._lon.value())
        if ok:
            self.accept()
        else:
            self._status.setText(
                lang.get("geotag_failed", "Failed to write GPS tags."))


def open_gps_geotag(viewer: "GPUImageView") -> None:
    path = getattr(viewer, "current_image_path", None) if viewer else None
    if not path:
        return
    GpsGeotagDialog(viewer, str(path)).exec()
